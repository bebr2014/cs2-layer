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