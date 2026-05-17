class MCPError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(MCPError):
    def __init__(self, resource: str, id: str) -> None:
        super().__init__("NOT_FOUND", f"{resource} '{id}' not found")


class PermissionError_(MCPError):
    def __init__(self, permission: str) -> None:
        super().__init__("FORBIDDEN", f"Missing permission: {permission}")


class TenantIsolationError(MCPError):
    def __init__(self) -> None:
        super().__init__("TENANT_ISOLATION", "Access denied — cross-tenant query blocked")


class ValidationError_(MCPError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__("VALIDATION_ERROR", f"{field}: {message}")
