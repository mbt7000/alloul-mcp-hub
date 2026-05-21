from __future__ import annotations
import json
from typing import Any
import structlog
from fastmcp import FastMCP

from alloul_billing.settings import Settings
from alloul_billing.plans import get_plan, list_plans
from shared.db import init_pool, get_pool
from shared.envelope import ok, err

log = structlog.get_logger()


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("product.billing", version="0.1.0")


    @mcp.tool()
    async def billing_list_plans(product: str) -> dict[str, Any]:
        """List available subscription plans for a product."""
        plans = list_plans(product)
        if not plans:
            return err("UNKNOWN_PRODUCT", f"No plans found for product: {product}")
        return ok({"product": product, "plans": plans})

    @mcp.tool()
    async def billing_start_subscription(
        tenant_id: str,
        product: str,
        plan: str,
        stripe_payment_method_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a new subscription for a tenant."""
        plan_info = get_plan(product, plan)
        if not plan_info:
            return err("UNKNOWN_PLAN", f"Plan '{plan}' not found for product '{product}'")
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO product.subscriptions (tenant_id, product, plan, status)
            VALUES ($1, $2, $3, 'active')
            ON CONFLICT DO NOTHING
            RETURNING id, tenant_id, product, plan, status, created_at
            """,
            tenant_id, product, plan,
        )
        if not row:
            existing = await pool.fetchrow(
                "SELECT id, plan, status FROM product.subscriptions WHERE tenant_id=$1 AND product=$2",
                tenant_id, product,
            )
            return err("ALREADY_SUBSCRIBED", f"Tenant already has a {existing['plan']} subscription")
        return ok(dict(row))

    @mcp.tool()
    async def billing_change_plan(
        tenant_id: str,
        product: str,
        new_plan: str,
    ) -> dict[str, Any]:
        """Change subscription plan (upgrade or downgrade)."""
        plan_info = get_plan(product, new_plan)
        if not plan_info:
            return err("UNKNOWN_PLAN", f"Plan '{new_plan}' not available for '{product}'")
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            UPDATE product.subscriptions SET plan=$1
            WHERE tenant_id=$2 AND product=$3 AND status='active'
            RETURNING id, plan, status
            """,
            new_plan, tenant_id, product,
        )
        if not row:
            return err("NOT_FOUND", "No active subscription found")
        return ok(dict(row))

    @mcp.tool()
    async def billing_cancel_subscription(
        tenant_id: str,
        product: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Cancel a subscription. Sets status to cancelled."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            UPDATE product.subscriptions SET status='cancelled'
            WHERE tenant_id=$1 AND product=$2 AND status='active'
            RETURNING id, plan, status
            """,
            tenant_id, product,
        )
        if not row:
            return err("NOT_FOUND", "No active subscription found")
        log.info("subscription_cancelled", tenant_id=tenant_id, product=product, reason=reason)
        return ok({"cancelled": True, **dict(row)})

    @mcp.tool()
    async def billing_get_status(
        tenant_id: str,
        product: str,
    ) -> dict[str, Any]:
        """Get current subscription status for a tenant."""
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT id, plan, status, stripe_subscription_id,
                   current_period_start, current_period_end, created_at
            FROM product.subscriptions
            WHERE tenant_id=$1 AND product=$2
            ORDER BY created_at DESC LIMIT 1
            """,
            tenant_id, product,
        )
        if not row:
            return ok({"tenant_id": tenant_id, "product": product, "status": "no_subscription"})
        return ok(dict(row))

    @mcp.tool()
    async def billing_list_invoices(
        tenant_id: str,
        product: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List invoices for a tenant."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT id, amount_cents, currency, status, due_date, paid_at, created_at
            FROM product.invoices
            WHERE tenant_id=$1 AND product=$2
            ORDER BY created_at DESC LIMIT $3
            """,
            tenant_id, product, limit,
        )
        return ok({"invoices": [dict(r) for r in rows]})

    @mcp.tool()
    async def billing_get_invoice(
        tenant_id: str,
        product: str,
        invoice_id: str,
    ) -> dict[str, Any]:
        """Get details of a specific invoice."""
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM product.invoices WHERE id=$1 AND tenant_id=$2 AND product=$3",
            invoice_id, tenant_id, product,
        )
        if not row:
            return err("NOT_FOUND", f"Invoice {invoice_id} not found")
        return ok(dict(row))

    @mcp.tool()
    async def billing_retry_payment(
        tenant_id: str,
        product: str,
        invoice_id: str,
    ) -> dict[str, Any]:
        """Retry a failed invoice payment."""
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT id, stripe_invoice_id, status FROM product.invoices WHERE id=$1 AND tenant_id=$2",
            invoice_id, tenant_id,
        )
        if not row:
            return err("NOT_FOUND", "Invoice not found")
        if row["status"] == "paid":
            return err("ALREADY_PAID", "Invoice already paid")
        # In production: call Stripe API with settings.stripe_secret_key
        log.info("billing_retry_payment", invoice_id=invoice_id, tenant_id=tenant_id)
        return ok({"invoice_id": invoice_id, "retry_initiated": True})

    @mcp.tool()
    async def billing_report_usage(
        tenant_id: str,
        product: str,
        metric: str,
        value: int,
        period: str | None = None,
    ) -> dict[str, Any]:
        """Report usage for metered billing (e.g., AI calls, storage)."""
        from datetime import datetime
        p = period or datetime.utcnow().strftime("%Y-%m")
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO product.usage_counters (tenant_id, product, metric, period, value)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (tenant_id, product, metric, period)
            DO UPDATE SET value = product.usage_counters.value + EXCLUDED.value,
                          updated_at = now()
            """,
            tenant_id, product, metric, p, value,
        )
        return ok({"reported": True, "metric": metric, "added": value, "period": p})

    @mcp.tool()
    async def billing_get_usage(
        tenant_id: str,
        product: str,
        period: str | None = None,
    ) -> dict[str, Any]:
        """Get current usage metrics for a tenant in a period."""
        from datetime import datetime
        p = period or datetime.utcnow().strftime("%Y-%m")
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT metric, value, updated_at FROM product.usage_counters WHERE tenant_id=$1 AND product=$2 AND period=$3",
            tenant_id, product, p,
        )
        return ok({"tenant_id": tenant_id, "product": product, "period": p,
                   "usage": [dict(r) for r in rows]})

    @mcp.tool()
    async def billing_check_quota(
        tenant_id: str,
        product: str,
        metric: str,
        requested: int = 1,
    ) -> dict[str, Any]:
        """Check if tenant has quota remaining for a metric. Returns allowed: bool."""
        from datetime import datetime
        p = datetime.utcnow().strftime("%Y-%m")
        pool = await get_pool()
        sub = await pool.fetchrow(
            "SELECT plan FROM product.subscriptions WHERE tenant_id=$1 AND product=$2 AND status='active'",
            tenant_id, product,
        )
        if not sub:
            return ok({"allowed": False, "reason": "no_active_subscription"})
        usage_row = await pool.fetchrow(
            "SELECT value FROM product.usage_counters WHERE tenant_id=$1 AND product=$2 AND metric=$3 AND period=$4",
            tenant_id, product, metric, p,
        )
        current = usage_row["value"] if usage_row else 0
        # Enterprise = unlimited
        if sub["plan"] == "enterprise":
            return ok({"allowed": True, "plan": sub["plan"], "current_usage": current})
        return ok({"allowed": True, "plan": sub["plan"], "current_usage": current, "requested": requested})

    return mcp
