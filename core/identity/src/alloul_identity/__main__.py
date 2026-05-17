import asyncio
from alloul_identity.server import create_server
from alloul_identity.settings import Settings

async def main() -> None:
    s = Settings()
    mcp = create_server(s)
    await mcp.run_http_async(host="0.0.0.0", port=s.port)

if __name__ == "__main__":
    asyncio.run(main())
