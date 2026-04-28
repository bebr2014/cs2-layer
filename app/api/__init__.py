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
@app.get("/test-ggsel-office")
async def test_ggsel_office():
    from app.clients.ggsel import ggsel_office
    try:
        token = await ggsel_office._get_token()
        return {"token": token[:30] + "..."}
    except Exception as e:
        return {"error": str(e)}
@app.get("/test-ggsel-urls")
async def test_ggsel_urls():
    import httpx
    from app.config import settings
    urls = [
        "https://ggsel.net/api_seller_office/v1/oauth/token",
        "https://seller.ggsel.net/api_seller_office/v1/oauth/token",
        "https://office.ggsel.net/api_seller_office/v1/oauth/token",
        "https://seller.ggsel.com/api_seller_office/v1/oauth/token",
    ]
    results = {}
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.post(
                    url,
                    headers={"locale": "ru"},
                    json={"grant_type": "password", "email": settings.ggsel_so_username, "password": settings.ggsel_so_password}
                )
                results[url] = {"status": resp.status_code, "body": resp.text[:100]}
            except Exception as e:
                results[url] = str(e)
    return results
@app.get("/reset-task")
async def reset_task():
    from app.db import AsyncSessionLocal
    from app.db.models import Task, TaskStatus
    from sqlalchemy import select
    from datetime import datetime
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Task).where(Task.id == 1))
        task = result.scalar_one_or_none()
        if task:
            task.status = TaskStatus.pending
            task.attempts = 0
            task.last_error = None
            task.scheduled_at = datetime.utcnow()
            await db.commit()
            return {"status": "reset"}
        return {"status": "not found"}

@app.get("/test-alert")
async def test_alert():
    from app.alerts import critical
    await critical("Test alert from cs2-layer!")
    return {"status": "sent"}

@app.get("/test-categories")
async def test_categories():
    from app.clients.ggsel import ggsel_office
    import httpx
    token = await ggsel_office._get_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://seller.ggsel.com/api/v1/categories",
            headers={"locale": "ru", "Cookie": f"ACCESS_TOKEN={token}"},
            params={"parent_id": 5, "limit": 100}
        )
        data = resp.json()
        # Ищем CS2
        cs2 = [c for c in data.get("data", []) if "CS" in c.get("title", "") or "Counter" in c.get("title", "")]
        return {"cs2_categories": cs2, "all": data}