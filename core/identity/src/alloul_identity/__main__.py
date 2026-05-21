import asyncio
from alloul_identity.server import create_server
from alloul_identity.settings import Settings
from shared.db import init_pool
from shared.telemetry import configure_logging

async def main() -> None:
    s = Settings()
    configure_logging(s.log_level)
    await init_pool(s.database_url)
    mcp = create_server(s)
    await mcp.run_http_async(host='0.0.0.0', port=s.port)

if __name__ == '__main__':
    asyncio.run(main())
