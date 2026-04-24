from fastapi import FastAPI
from app.api.webhooks import router

app = FastAPI(title="cs2-layer")
app.include_router(router)

@app.get("/")
async def root():
    return {"status": "ok"}
@app.get("/myip")
async def myip():
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.ipify.org?format=json")
        return resp.json()
@app.get("/test-xpanda")
async def test_xpanda():
    import httpx
    from app.config import settings
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://p2p.xpanda.pro/api/v1/balance/",
            headers={"Authorization": settings.xpanda_api_key}
        )
        return {"status": resp.status_code, "body": resp.json()}