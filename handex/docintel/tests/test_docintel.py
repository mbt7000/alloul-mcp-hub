import pytest

@pytest.mark.asyncio
async def test_server_creates() -> None:
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://a:b@localhost/c")
    from handex_docintel.settings import Settings
    from handex_docintel.server import create_server
    mcp = create_server(Settings())
    assert mcp is not None
