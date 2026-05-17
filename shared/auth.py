from __future__ import annotations
import time
from typing import Any
import jwt as pyjwt


def verify_jwt(token: str, secret: str) -> dict[str, Any]:
    """Verify and decode a JWT. Raises jwt.InvalidTokenError on failure."""
    return pyjwt.decode(token, secret, algorithms=["HS256"])  # type: ignore[no-any-return]


def issue_service_token(
    service: str,
    target: str,
    secret: str,
    ttl_seconds: int = 300,
) -> str:
    payload = {
        "sub": f"service:{service}",
        "aud": target,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
        "type": "service",
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def issue_user_token(
    user_id: str,
    tenant_id: str,
    product: str,
    permissions: list[str],
    secret: str,
    ttl_seconds: int = 3600,
) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "product": product,
        "permissions": permissions,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
        "type": "user",
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")
