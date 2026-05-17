from __future__ import annotations
import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool(database_url: str, min_size: int = 2, max_size: int = 10) -> None:
    global _pool
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    _pool = await asyncpg.create_pool(url, min_size=min_size, max_size=max_size)


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() first")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
