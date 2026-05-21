from __future__ import annotations
import hashlib
import random
import string
import time
from typing import Any
import asyncpg
import jwt as pyjwt
import structlog

from fastmcp import FastMCP
from alloul_identity.settings import Settings
from shared.db import init_pool, get_pool
from shared.envelope import ok, err
from shared.auth import issue_user_token, issue_service_token

log = structlog.get_logger()

YEAR = 2026


def _gen_employee_code(prefix: str) -> str:
    part1 = str(YEAR)
    part2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part3 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{part1}-{part2}-{part3}"


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("alloul.identity", version="0.1.0")


    @mcp.tool()
    async def identity_whoami(token: str) -> dict[str, Any]:
        """Resolve a JWT token to user context."""
        try:
            payload = pyjwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        except pyjwt.InvalidTokenError as e:
            return err("INVALID_TOKEN", str(e))
        return ok({
            "user_id": payload.get("sub"),
            "tenant_id": payload.get("tenant_id"),
            "product": payload.get("product"),
            "permissions": payload.get("permissions", []),
            "type": payload.get("type", "user"),
        })

    @mcp.tool()
    async def identity_register_tenant(
        name: str,
        product: str,
        plan: str = "starter",
    ) -> dict[str, Any]:
        """Register a new tenant (customer) under a product."""
        if product not in ("alloulq", "handex"):
            return err("INVALID_PRODUCT", "product must be alloulq or handex")
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO alloul_core.tenants (name, product, plan)
            VALUES ($1, $2, $3)
            RETURNING id, name, product, plan, status, created_at
            """,
            name, product, plan,
        )
        return ok(dict(row))

    @mcp.tool()
    async def identity_register_employee(
        tenant_id: str,
        product: str,
        name: str,
        email: str,
        role: str = "member",
    ) -> dict[str, Any]:
        """Register employee with auto-generated EMP-YYYY-XXXX-XXXX code."""
        pool = await get_pool()
        for _ in range(5):
            code = _gen_employee_code(settings.employee_code_prefix)
            try:
                row = await pool.fetchrow(
                    """
                    INSERT INTO alloul_core.employees (tenant_id, product, employee_code, name, email, role)
                    VALUES ($1,$2,$3,$4,$5,$6)
                    RETURNING id, tenant_id, employee_code, name, email, role, status, created_at
                    """,
                    tenant_id, product, code, name, email, role,
                )
                return ok(dict(row))
            except asyncpg.UniqueViolationError as e:
                if "employee_code" in str(e):
                    continue
                return err("DUPLICATE", "Employee with this email already exists in tenant")
        return err("CODE_COLLISION", "Failed to generate unique employee code")

    @mcp.tool()
    async def identity_grant_permission(
        employee_id: str,
        permission: str,
        granted_by: str | None = None,
    ) -> dict[str, Any]:
        """Grant a permission to an employee."""
        pool = await get_pool()
        emp = await pool.fetchrow(
            "SELECT tenant_id FROM alloul_core.employees WHERE id=$1", employee_id,
        )
        if not emp:
            return err("NOT_FOUND", f"Employee {employee_id} not found")
        await pool.execute(
            """
            INSERT INTO alloul_core.permissions (tenant_id, employee_id, permission, granted_by)
            VALUES ($1,$2,$3,$4)
            ON CONFLICT (employee_id, permission) DO NOTHING
            """,
            str(emp["tenant_id"]), employee_id, permission, granted_by,
        )
        return ok({"employee_id": employee_id, "permission": permission, "granted": True})

    @mcp.tool()
    async def identity_check_permission(
        employee_id: str,
        permission: str,
    ) -> dict[str, Any]:
        """Check if an employee has a specific permission. Returns boolean."""
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT id FROM alloul_core.permissions WHERE employee_id=$1 AND permission=$2",
            employee_id, permission,
        )
        return ok({"has_permission": row is not None, "employee_id": employee_id, "permission": permission})

    @mcp.tool()
    async def identity_list_employees(
        tenant_id: str,
        product: str,
        role: str | None = None,
        status: str = "active",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List employees for a tenant with optional filters. Tenant-isolated."""
        pool = await get_pool()
        if role:
            rows = await pool.fetch(
                """
                SELECT id, employee_code, name, email, role, status, created_at
                FROM alloul_core.employees
                WHERE tenant_id=$1 AND product=$2 AND status=$3 AND role=$4
                ORDER BY created_at DESC LIMIT $5 OFFSET $6
                """,
                tenant_id, product, status, role, limit, offset,
            )
        else:
            rows = await pool.fetch(
                """
                SELECT id, employee_code, name, email, role, status, created_at
                FROM alloul_core.employees
                WHERE tenant_id=$1 AND product=$2 AND status=$3
                ORDER BY created_at DESC LIMIT $4 OFFSET $5
                """,
                tenant_id, product, status, limit, offset,
            )
        return ok({"employees": [dict(r) for r in rows], "count": len(rows)})

    @mcp.tool()
    async def identity_issue_service_token(
        service: str,
        target: str,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        """Issue a short-lived service-to-service JWT."""
        token = issue_service_token(service, target, settings.jwt_secret_key, ttl_seconds)
        return ok({"token": token, "service": service, "target": target, "ttl_seconds": ttl_seconds})

    @mcp.tool()
    async def identity_issue_user_token(
        user_id: str,
        tenant_id: str,
        product: str,
        ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Issue a user JWT with their current permissions."""
        pool = await get_pool()
        perms = await pool.fetch(
            "SELECT permission FROM alloul_core.permissions WHERE employee_id=$1",
            user_id,
        )
        permissions = [r["permission"] for r in perms]
        token = issue_user_token(user_id, tenant_id, product, permissions, settings.jwt_secret_key, ttl_seconds)
        return ok({"token": token, "user_id": user_id, "permissions": permissions})

    @mcp.tool()
    async def identity_audit_query(
        tenant_id: str,
        product: str,
        service: str | None = None,
        resource_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query audit log for a tenant. Tenant-isolated."""
        pool = await get_pool()
        filters = ["tenant_id=$1", "product=$2"]
        params: list[Any] = [tenant_id, product]
        idx = 3
        if service:
            filters.append(f"service=${idx}")
            params.append(service)
            idx += 1
        if resource_type:
            filters.append(f"resource_type=${idx}")
            params.append(resource_type)
            idx += 1
        params.extend([limit, offset])
        where = " AND ".join(filters)
        rows = await pool.fetch(
            f"""
            SELECT id, service, tool, action, resource_type, resource_id, user_id, created_at
            FROM alloul_core.audit_log
            WHERE {where}
            ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}
            """,
            *params,
        )
        return ok({"logs": [dict(r) for r in rows], "count": len(rows)})

    return mcp
