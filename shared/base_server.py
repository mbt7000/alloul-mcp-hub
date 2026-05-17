from __future__ import annotations
from fastmcp import FastMCP
from shared.settings import BaseSettings_
from shared.db import init_pool, close_pool
from shared.telemetry import configure_logging
import structlog

log = structlog.get_logger()


def make_server(name: str, version: str = "0.1.0") -> FastMCP:
    return FastMCP(name, version=version)


async def startup_db(settings: BaseSettings_) -> None:
    configure_logging(settings.log_level)
    await init_pool(settings.database_url)
    log.info("server_started", name="alloul-mcp-hub")


async def shutdown_db() -> None:
    await close_pool()
