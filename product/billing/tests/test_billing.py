import pytest

@pytest.mark.asyncio
async def test_server_creates() -> None:
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://a:b@localhost/c")
    from alloul_billing.settings import Settings
    from alloul_billing.server import create_server
    mcp = create_server(Settings())
    assert mcp is not None

@pytest.mark.asyncio
async def test_list_plans_alloulq() -> None:
    from alloul_billing.plans import list_plans
    plans = list_plans("alloulq")
    names = [p["name"] for p in plans]
    assert "starter" in names
    assert "pro" in names
    assert "business" in names

@pytest.mark.asyncio
async def test_list_plans_unknown() -> None:
    from alloul_billing.plans import list_plans
    plans = list_plans("unknown_product")
    assert plans == []
