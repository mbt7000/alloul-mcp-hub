import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))


@pytest.mark.asyncio
async def test_employee_code_format() -> None:
    from alloul_identity.server import _gen_employee_code
    code = _gen_employee_code("EMP")
    parts = code.split("-")
    assert len(parts) == 4
    assert parts[0] == "EMP"
    assert len(parts[1]) == 4
    assert len(parts[2]) == 4
    assert len(parts[3]) == 4


@pytest.mark.asyncio
async def test_server_creates() -> None:
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://a:b@localhost/c")
    os.environ.setdefault("JWT_SECRET_KEY", "test")
    from alloul_identity.settings import Settings
    from alloul_identity.server import create_server
    s = Settings()
    mcp = create_server(s)
    assert mcp is not None
