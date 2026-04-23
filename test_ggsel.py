import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.ipify.org?format=json")
        print("Our IP:", resp.json()["ip"])

asyncio.run(main())