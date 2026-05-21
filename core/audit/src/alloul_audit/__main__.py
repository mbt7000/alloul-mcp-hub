import asyncio
from alloul_audit.server import create_server
from alloul_audit.settings import Settings
from shared.db import init_pool

async def main() -> None:
    s = Settings()
    await init_pool(s.database_url)
    mcp = create_server(s)
    await mcp.run_http_async(host='0.0.0.0', port=s.port)

if __name__ == '__main__':
    asyncio.run(main())
