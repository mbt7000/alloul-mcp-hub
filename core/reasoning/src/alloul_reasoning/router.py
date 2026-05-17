from __future__ import annotations
from alloul_reasoning.providers.base import BaseProvider, LLMRequest
from shared.db import get_pool
from datetime import datetime


async def _budget_pct(tenant_id: str) -> float:
    try:
        pool = await get_pool()
        period = datetime.utcnow().strftime("%Y-%m")
        row = await pool.fetchrow(
            "SELECT limit_usd_micros, current_usd_micros FROM alloul_core.llm_budgets WHERE tenant_id=$1 AND period=$2",
            tenant_id, period,
        )
        if not row or row["limit_usd_micros"] == 0:
            return 100.0
        remaining = max(0, row["limit_usd_micros"] - row["current_usd_micros"])
        return (remaining / row["limit_usd_micros"]) * 100.0
    except Exception:
        return 100.0


async def select_chain(
    request: LLMRequest,
    providers: dict[str, BaseProvider],
) -> list[BaseProvider]:
    if request.privacy == "high":
        if "ollama" in providers:
            return [providers["ollama"]]
        raise ValueError("No local provider for privacy=high")
    chain: list[BaseProvider] = []
    pct = 100.0
    if request.tenant_id:
        pct = await _budget_pct(request.tenant_id)
    if pct >= 10.0 and "claude" in providers:
        chain.append(providers["claude"])
    if "deepseek" in providers:
        chain.append(providers["deepseek"])
    if "ollama" in providers:
        chain.append(providers["ollama"])
    return chain
