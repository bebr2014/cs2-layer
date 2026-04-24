import asyncio
import httpx
from app.config import settings

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://p2p.xpanda.pro/api/v1/balance/",
            headers={"Authorization": settings.xpanda_api_key}
        )
        print(resp.status_code, resp.text)

asyncio.run(main())