import pytest

@pytest.mark.asyncio
async def test_server_creates() -> None:
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://a:b@localhost/c")
    from alloul_analytics.settings import Settings
    from alloul_analytics.server import create_server
    mcp = create_server(Settings())
    assert mcp is not None
