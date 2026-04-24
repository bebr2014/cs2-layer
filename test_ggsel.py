import asyncio
from app.clients.ggsel import ggsel_office

async def main():
    token = await ggsel_office._get_token()
    print(f"Office Token: {token[:30]}...")

asyncio.run(main())