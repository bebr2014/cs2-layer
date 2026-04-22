import asyncio
from app.clients.ggsel import ggsel_seller

async def main():
    token = await ggsel_seller._get_token()
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        # Перебираем страницы
        for page in range(1, 10):
            resp = await client.get(
                "https://seller.ggsel.com/api_sellers/api/categories",
                params={"token": token, "page": page, "count": 100},
                headers={"lang": "ru-RU"}
            )
            data = resp.json()
            cats = data.get("category", [])
            if not cats:
                print(f"Page {page}: empty, stop")
                break
            for cat in cats:
                if "CS" in cat["name"] or "cs" in cat["name"].lower() or "steam" in cat["name"].lower():
                    print(f"FOUND: id={cat['id']} name={cat['name']}")
                for sub in cat.get("sub", []):
                    if "CS" in sub["name"] or "cs" in sub["name"].lower():
                        print(f"  SUB: id={sub['id']} name={sub['name']}")

asyncio.run(main())