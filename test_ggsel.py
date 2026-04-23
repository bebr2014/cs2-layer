import asyncio
from app.fx import get_usd_rub

async def main():
    rate = await get_usd_rub()
    print(f"USD/RUB = {rate}")

asyncio.run(main())