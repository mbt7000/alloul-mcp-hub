from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TenantContext:
    tenant_id: str
    product: str  # "alloulq" | "handex"
    user_id: str | None = None
    permissions: list[str] | None = None

    def has_permission(self, permission: str) -> bool:
        if self.permissions is None:
            return False
        return permission in self.permissions

    def require_permission(self, permission: str) -> None:
        if not self.has_permission(permission):
            from shared.errors import PermissionError_
            raise PermissionError_(permission)
