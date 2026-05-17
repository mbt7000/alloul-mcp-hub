from __future__ import annotations
import hashlib, json, uuid
from typing import Any
import redis.asyncio as aioredis
import structlog
from fastmcp import FastMCP
from alloul_reasoning.settings import Settings
from alloul_reasoning.providers.base import LLMRequest
from alloul_reasoning.providers.claude import ClaudeProvider
from alloul_reasoning.providers.deepseek import DeepSeekProvider
from alloul_reasoning.providers.ollama import OllamaProvider
from alloul_reasoning.router import select_chain
from shared.db import init_pool, get_pool
from shared.envelope import ok, err

log = structlog.get_logger()


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("alloul.reasoning", version="0.1.0")
    _redis: aioredis.Redis | None = None

    providers: dict = {}
    if settings.anthropic_api_key:
        providers["claude"] = ClaudeProvider(settings)
    if settings.deepseek_api_key:
        providers["deepseek"] = DeepSeekProvider(settings)
    providers["ollama"] = OllamaProvider(settings)

    @mcp.on_startup
    async def startup() -> None:
        nonlocal _redis
        await init_pool(settings.database_url)
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        log.info("alloul.reasoning started", providers=list(providers.keys()))

    async def _run(req: LLMRequest) -> dict[str, Any]:
        chain = await select_chain(req, providers)
        fallback_from: str | None = None
        for provider in chain:
            try:
                resp = await provider.complete(req)
                return {
                    "text": resp.text, "provider_used": resp.provider, "model_used": resp.model,
                    "usage": {"prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens, "cached_tokens": resp.cached_tokens},
                    "cost_usd_micros": resp.cost_usd_micros, "latency_ms": resp.latency_ms,
                    "fallback_from": fallback_from,
                }
            except Exception as e:
                err_str = str(e)
                if any(f" {c}" in err_str or f"status_code={c}" in err_str for c in [400, 401, 403]):
                    raise
                log.warning("provider_failed", provider=provider.name, error=err_str[:200])
                fallback_from = provider.name
        raise RuntimeError("All providers failed")

    @mcp.tool()
    async def reasoning_complete(
        messages: list[dict[str, Any]],
        tenant_id: str | None = None,
        caller_service: str = "unknown",
        caller_tool: str = "unknown",
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model_hint: str | None = None,
        privacy: str = "normal",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Complete a chat conversation using the best available LLM."""
        req = LLMRequest(messages=messages, system=system, max_tokens=max_tokens,
                         temperature=temperature, model_hint=model_hint,
                         privacy=privacy, tenant_id=tenant_id,
                         caller_service=caller_service, caller_tool=caller_tool,
                         trace_id=trace_id or str(uuid.uuid4()))
        return await _run(req)

    @mcp.tool()
    async def reasoning_structured(
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any],
        tenant_id: str | None = None,
        caller_service: str = "unknown",
        caller_tool: str = "unknown",
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        privacy: str = "normal",
    ) -> dict[str, Any]:
        """Complete with structured JSON output. Auto-retries up to 3 times on invalid JSON."""
        req = LLMRequest(messages=messages, system=system, max_tokens=max_tokens,
                         temperature=temperature, json_schema=json_schema,
                         privacy=privacy, tenant_id=tenant_id,
                         caller_service=caller_service, caller_tool=caller_tool)
        result: dict[str, Any] = {}
        for attempt in range(3):
            result = await _run(req)
            try:
                parsed = json.loads(result["text"]) if isinstance(result["text"], str) else result["text"]
                result["parsed"] = parsed
                return result
            except (json.JSONDecodeError, TypeError):
                if attempt == 2:
                    result["parsed"] = None
                    return result
                req.messages = req.messages + [
                    {"role": "assistant", "content": result["text"]},
                    {"role": "user", "content": f"Invalid JSON. Respond ONLY with JSON matching: {json.dumps(json_schema)}"},
                ]
        return result

    @mcp.tool()
    async def reasoning_usage_report(
        tenant_id: str,
        period: str | None = None,
    ) -> dict[str, Any]:
        """Per-tenant LLM usage statistics."""
        from datetime import datetime
        p = period or datetime.utcnow().strftime("%Y-%m")
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT provider, caller_service, count(*) AS calls,
                   sum(cost_usd_micros) AS cost_micros, avg(latency_ms) AS avg_latency
            FROM alloul_core.llm_calls
            WHERE tenant_id=$1 AND date_trunc('month', created_at)=to_timestamp($2,'YYYY-MM')
            GROUP BY provider, caller_service
            """,
            tenant_id, p,
        )
        return ok({"tenant_id": tenant_id, "period": p, "breakdown": [dict(r) for r in rows]})

    @mcp.tool()
    async def reasoning_budget_set(
        tenant_id: str,
        period: str,
        limit_usd: float,
        alert_threshold_pct: int = 80,
    ) -> dict[str, Any]:
        """Set monthly LLM budget for a tenant."""
        pool = await get_pool()
        micros = int(limit_usd * 1_000_000)
        await pool.execute(
            """
            INSERT INTO alloul_core.llm_budgets (tenant_id, period, limit_usd_micros, alert_threshold_pct)
            VALUES ($1,$2,$3,$4)
            ON CONFLICT (tenant_id, period) DO UPDATE
            SET limit_usd_micros=EXCLUDED.limit_usd_micros, alert_threshold_pct=EXCLUDED.alert_threshold_pct
            """,
            tenant_id, period, micros, alert_threshold_pct,
        )
        return ok({"tenant_id": tenant_id, "period": period, "limit_usd": limit_usd})

    return mcp
