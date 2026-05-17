from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Any
import redis.asyncio as aioredis
import structlog
from fastmcp import FastMCP

from alloul_analytics.settings import Settings
from shared.db import init_pool, get_pool
from shared.envelope import ok, err

log = structlog.get_logger()


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("alloul.analytics", version="0.1.0")
    _redis: aioredis.Redis | None = None

    @mcp.on_startup
    async def startup() -> None:
        nonlocal _redis
        await init_pool(settings.database_url)
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        log.info("alloul.analytics started")

    async def _cached(key: str, fn: Any) -> Any:
        if _redis:
            cached = await _redis.get(key)
            if cached:
                return json.loads(cached)
        result = await fn()
        if _redis:
            await _redis.setex(key, settings.cache_ttl_seconds, json.dumps(result, default=str))
        return result

    @mcp.tool()
    async def analytics_kpis_holdings(period_days: int = 30) -> dict[str, Any]:
        """
        Top-level Holdings KPIs. Requires holdings:read permission — enforced at gateway.
        Returns: active tenants by product, LLM costs, subscription revenue, RAG usage.
        """
        async def _compute() -> dict[str, Any]:
            pool = await get_pool()
            since = datetime.utcnow() - timedelta(days=period_days)

            tenant_rows = await pool.fetch(
                "SELECT product, count(*) AS count, count(*) FILTER (WHERE status='active') AS active FROM alloul_core.tenants GROUP BY product",
            )

            sub_rows = await pool.fetch(
                "SELECT product, plan, count(*) AS count FROM product.subscriptions WHERE status='active' GROUP BY product, plan ORDER BY product, plan",
            )

            llm_rows = await pool.fetch(
                """SELECT product_label, sum(cost_usd_micros) AS cost_micros, count(*) AS calls
                   FROM (
                       SELECT CASE WHEN caller_service LIKE '%handex%' THEN 'handex' ELSE 'alloulq' END AS product_label,
                              cost_usd_micros FROM alloul_core.llm_calls WHERE created_at >= $1
                   ) sub GROUP BY product_label""",
                since,
            )

            return {
                "period_days": period_days,
                "generated_at": datetime.utcnow().isoformat(),
                "tenants": [dict(r) for r in tenant_rows],
                "active_subscriptions": [dict(r) for r in sub_rows],
                "llm_costs": [dict(r) for r in llm_rows],
            }

        cache_key = f"analytics:holdings:{period_days}"
        return ok(await _cached(cache_key, _compute))

    @mcp.tool()
    async def analytics_kpis_product(
        product: str,
        period_days: int = 30,
    ) -> dict[str, Any]:
        """KPIs for a specific product (alloulq or handex)."""
        if product not in ("alloulq", "handex"):
            return err("INVALID_PRODUCT", "product must be alloulq or handex")

        pool = await get_pool()
        since = datetime.utcnow() - timedelta(days=period_days)

        tenants = await pool.fetchrow(
            "SELECT count(*) AS total, count(*) FILTER (WHERE status='active') AS active FROM alloul_core.tenants WHERE product=$1",
            product,
        )
        subs = await pool.fetch(
            "SELECT plan, count(*) AS count FROM product.subscriptions WHERE product=$1 AND status='active' GROUP BY plan",
            product,
        )
        llm = await pool.fetchrow(
            """SELECT count(*) AS calls, sum(cost_usd_micros) AS cost_micros, avg(latency_ms) AS avg_latency
               FROM alloul_core.llm_calls WHERE caller_service LIKE $1 AND created_at >= $2""",
            f"%{product}%", since,
        )
        rag = await pool.fetchrow(
            "SELECT count(*) AS collections, sum(c.cnt) AS total_chunks FROM knowledge.collections col LEFT JOIN (SELECT collection_id, count(*) AS cnt FROM knowledge.chunks GROUP BY collection_id) c ON c.collection_id=col.id WHERE col.product=$1",
            product,
        )

        return ok({
            "product": product,
            "period_days": period_days,
            "tenants": dict(tenants) if tenants else {},
            "subscriptions": [dict(r) for r in subs],
            "llm": dict(llm) if llm else {},
            "rag": dict(rag) if rag else {},
        })

    @mcp.tool()
    async def analytics_kpis_tenant(
        tenant_id: str,
        period_days: int = 30,
    ) -> dict[str, Any]:
        """Per-tenant KPIs including usage, expansion signals, and churn indicators."""
        pool = await get_pool()
        since = datetime.utcnow() - timedelta(days=period_days)

        llm_rows = await pool.fetch(
            """SELECT provider, caller_tool, count(*) AS calls, sum(cost_usd_micros) AS cost_micros
               FROM alloul_core.llm_calls WHERE tenant_id=$1 AND created_at>=$2
               GROUP BY provider, caller_tool ORDER BY cost_micros DESC""",
            tenant_id, since,
        )
        sub = await pool.fetchrow(
            "SELECT plan, status, current_period_end FROM product.subscriptions WHERE tenant_id=$1 AND status='active' LIMIT 1",
            tenant_id,
        )
        budget = await pool.fetchrow(
            "SELECT limit_usd_micros, current_usd_micros FROM alloul_core.llm_budgets WHERE tenant_id=$1 AND period=$2",
            tenant_id, datetime.utcnow().strftime("%Y-%m"),
        )

        total_cost = sum(r["cost_micros"] or 0 for r in llm_rows)
        expansion = False
        if budget:
            pct = (budget["current_usd_micros"] / max(budget["limit_usd_micros"], 1)) * 100
            expansion = pct >= 80

        return ok({
            "tenant_id": tenant_id,
            "period_days": period_days,
            "total_llm_cost_usd": total_cost / 1_000_000,
            "subscription": dict(sub) if sub else None,
            "budget_status": dict(budget) if budget else None,
            "expansion_signal": expansion,
            "llm_breakdown": [dict(r) for r in llm_rows],
        })

    @mcp.tool()
    async def analytics_weekly_executive() -> dict[str, Any]:
        """Generate weekly executive report as Markdown. Holdings-level view."""
        pool = await get_pool()
        now = datetime.utcnow()
        since = now - timedelta(days=7)
        prev_since = since - timedelta(days=7)

        cur = await pool.fetchrow(
            "SELECT count(*) AS calls, sum(cost_usd_micros) AS cost_micros, count(DISTINCT tenant_id) AS active_tenants FROM alloul_core.llm_calls WHERE created_at>=$1",
            since,
        )
        prev = await pool.fetchrow(
            "SELECT count(*) AS calls, sum(cost_usd_micros) AS cost_micros FROM alloul_core.llm_calls WHERE created_at>=$1 AND created_at<$2",
            prev_since, since,
        )
        providers = await pool.fetch(
            "SELECT provider, count(*) AS calls, sum(cost_usd_micros) AS cost_micros FROM alloul_core.llm_calls WHERE created_at>=$1 GROUP BY provider",
            since,
        )
        new_tenants = await pool.fetchrow(
            "SELECT count(*) AS count FROM alloul_core.tenants WHERE created_at>=$1", since,
        )

        cur_cost = (cur["cost_micros"] or 0) / 1_000_000
        prev_cost = (prev["cost_micros"] or 0) / 1_000_000
        chg = ((cur_cost - prev_cost) / max(prev_cost, 0.001)) * 100

        report = f"""# Alloul Holdings — Weekly Executive Report
**{since.strftime('%Y-%m-%d')} -> {now.strftime('%Y-%m-%d')}**

## Summary
| Metric | This Week | Delta |
|--------|-----------|-------|
| LLM Cost | ${cur_cost:.2f} | {chg:+.1f}% |
| AI Calls | {cur['calls']:,} | — |
| Active Tenants | {cur['active_tenants']} | — |
| New Tenants | {new_tenants['count']} | — |

## LLM by Provider
"""
        for p in providers:
            cost = (p["cost_micros"] or 0) / 1_000_000
            report += f"- **{p['provider'].title()}**: {p['calls']:,} calls | ${cost:.2f}\n"

        return ok({"markdown": report, "generated_at": now.isoformat()})

    @mcp.tool()
    async def analytics_churn_risk(threshold_days_inactive: int = 14) -> dict[str, Any]:
        """Detect tenants with declining usage — potential churn signals."""
        pool = await get_pool()
        now = datetime.utcnow()
        window = now - timedelta(days=threshold_days_inactive)

        rows = await pool.fetch(
            """
            WITH recent AS (
                SELECT tenant_id, max(created_at) AS last_call, count(*) AS recent_calls
                FROM alloul_core.llm_calls WHERE created_at>=$1 GROUP BY tenant_id
            ),
            hist AS (
                SELECT tenant_id, count(*) AS hist_calls
                FROM alloul_core.llm_calls WHERE created_at>=$2 AND created_at<$1
                GROUP BY tenant_id
            )
            SELECT h.tenant_id, COALESCE(r.recent_calls,0) AS recent, h.hist_calls AS historical,
                   r.last_call,
                   CASE WHEN COALESCE(r.recent_calls,0)=0 THEN 'no_activity'
                        WHEN COALESCE(r.recent_calls,0)<h.hist_calls*0.5 THEN 'high'
                        WHEN COALESCE(r.recent_calls,0)<h.hist_calls*0.7 THEN 'medium'
                        ELSE 'low' END AS risk_level
            FROM hist h LEFT JOIN recent r ON r.tenant_id=h.tenant_id
            WHERE COALESCE(r.recent_calls,0)<h.hist_calls*0.7
            ORDER BY recent ASC
            """,
            window, window - timedelta(days=threshold_days_inactive),
        )
        return ok({"at_risk": [dict(r) for r in rows], "threshold_days": threshold_days_inactive})

    @mcp.tool()
    async def analytics_expansion_signal() -> dict[str, Any]:
        """Detect tenants near plan limits — upsell opportunities."""
        pool = await get_pool()
        period = datetime.utcnow().strftime("%Y-%m")
        rows = await pool.fetch(
            """
            SELECT b.tenant_id, b.period, b.limit_usd_micros, b.current_usd_micros, b.alert_threshold_pct,
                   round(100.0*b.current_usd_micros/NULLIF(b.limit_usd_micros,0),1) AS pct_used
            FROM alloul_core.llm_budgets b
            WHERE b.period=$1
              AND b.current_usd_micros>=(b.limit_usd_micros*b.alert_threshold_pct/100)
            ORDER BY pct_used DESC
            """,
            period,
        )
        return ok({"expansion_candidates": [dict(r) for r in rows], "period": period})

    return mcp
