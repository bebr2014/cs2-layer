import asyncio
import httpx
from app.config import settings
from app.clients.ggsel import SELLER_OFFICE_V2_URL


async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SELLER_OFFICE_V2_URL}/offers",
            headers={"Authorization": settings.ggsel_api_key},
        )
        print(f"Status: {resp.status_code}")
        print(resp.text[:300])


asyncio.run(main())
