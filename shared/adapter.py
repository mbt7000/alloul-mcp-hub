from __future__ import annotations
from typing import Any
import httpx
import structlog

log = structlog.get_logger()


class HTTPBackendAdapter:
    """Wraps an HTTP backend (ALLOUL&Q or Handex) for MCP tools to call."""

    def __init__(self, base_url: str, service_token: str | None = None) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if service_token:
            headers["Authorization"] = f"Bearer {service_token}"
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=30.0,
        )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def post(self, path: str, data: dict[str, Any]) -> Any:
        resp = await self._client.post(path, json=data)
        resp.raise_for_status()
        return resp.json()

    async def patch(self, path: str, data: dict[str, Any]) -> Any:
        resp = await self._client.patch(path, json=data)
        resp.raise_for_status()
        return resp.json()

    async def delete(self, path: str) -> Any:
        resp = await self._client.delete(path)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
