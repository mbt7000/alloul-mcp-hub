from __future__ import annotations
import json
from typing import Any
from shared.db import get_pool


async def write(
    *,
    tenant_id: str,
    product: str,
    user_id: str | None,
    service: str,
    tool: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO alloul_core.audit_log
            (tenant_id, product, user_id, service, tool, action, resource_type, resource_id, payload)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """,
        tenant_id, product, user_id, service, tool, action,
        resource_type, resource_id, json.dumps(payload or {}),
    )
