from __future__ import annotations
import csv
import io
import json
from typing import Any
import structlog
from fastmcp import FastMCP
from alloul_audit.settings import Settings
from shared.db import init_pool, get_pool
from shared.envelope import ok, err

log = structlog.get_logger()


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("alloul.audit", version="0.1.0")

    @mcp.on_startup
    async def startup() -> None:
        await init_pool(settings.database_url)
        log.info("alloul.audit started")

    @mcp.tool()
    async def audit_write(
        tenant_id: str,
        product: str,
        service: str,
        tool: str,
        action: str,
        resource_type: str,
        user_id: str | None = None,
        resource_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write an audit log entry. Called by every MCP tool on mutations."""
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
        return ok({"logged": True})

    @mcp.tool()
    async def audit_query(
        tenant_id: str,
        product: str,
        service: str | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        since_iso: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query audit log with filters. Always scoped to tenant+product."""
        pool = await get_pool()
        filters = ["tenant_id=$1", "product=$2"]
        params: list[Any] = [tenant_id, product]
        idx = 3
        for val, col in [(service, "service"), (resource_type, "resource_type"), (action, "action")]:
            if val:
                filters.append(f"{col}=${idx}")
                params.append(val)
                idx += 1
        if since_iso:
            filters.append(f"created_at >= ${idx}::timestamptz")
            params.append(since_iso)
            idx += 1
        params.extend([limit, offset])
        where = " AND ".join(filters)
        rows = await pool.fetch(
            f"""
            SELECT id, service, tool, action, resource_type, resource_id, user_id, payload, created_at
            FROM alloul_core.audit_log WHERE {where}
            ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}
            """,
            *params,
        )
        return ok({"logs": [dict(r) for r in rows], "count": len(rows)})

    @mcp.tool()
    async def audit_export(
        tenant_id: str,
        product: str,
        format: str = "json",
        since_iso: str | None = None,
        until_iso: str | None = None,
    ) -> dict[str, Any]:
        """Export audit log for compliance. format: 'json' | 'csv'."""
        pool = await get_pool()
        params: list[Any] = [tenant_id, product]
        extra = ""
        if since_iso:
            extra += f" AND created_at >= ${len(params)+1}::timestamptz"
            params.append(since_iso)
        if until_iso:
            extra += f" AND created_at <= ${len(params)+1}::timestamptz"
            params.append(until_iso)
        rows = await pool.fetch(
            f"SELECT * FROM alloul_core.audit_log WHERE tenant_id=$1 AND product=$2{extra} ORDER BY created_at DESC LIMIT 10000",
            *params,
        )
        records = [dict(r) for r in rows]
        if format == "csv":
            buf = io.StringIO()
            if records:
                w = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
                w.writeheader()
                w.writerows(records)
            return ok({"csv": buf.getvalue(), "count": len(records)})
        return ok({"records": records, "count": len(records)})

    return mcp
