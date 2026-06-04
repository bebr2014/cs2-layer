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
    from app.clients.xpanda import xpanda
    data = await xpanda.get_prices()
    items = data.get("items", []) if isinstance(data, dict) else data
    return {"raw": data, "count": len(items), "first_3": items[:3]}
@app.get("/test-ggsel-office")
async def test_ggsel_office():
    import httpx
    from app.config import settings
    from app.clients.ggsel import SELLER_OFFICE_V2_URL
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SELLER_OFFICE_V2_URL}/offers",
                headers={"Authorization": settings.ggsel_api_key},
            )
            return {"status": resp.status_code, "body": resp.text[:200]}
    except Exception as e:
        return {"error": str(e)}
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
    import httpx
    from app.config import settings
    from app.clients.ggsel import SELLER_OFFICE_V2_URL
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{SELLER_OFFICE_V2_URL}/categories",
            headers={"Authorization": settings.ggsel_api_key},
            params={"parent_id": 16674, "limit": 100},
        )
        return resp.json()
@app.get("/debug-offer")
async def debug_offer():
    from app.db import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT * FROM offers WHERE id = 1"))
        row = result.fetchone()
        if row:
            return dict(row._mapping)
        return {"error": "not found"}


@app.get("/test-precheck")
async def test_precheck():
    import httpx
    from app.config import settings
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://cs2-layer-production.up.railway.app/hooks/ggsel/precheck/1?secret={settings.webhook_shared_secret}",
            json={
                "product": {"cnt": 1},
                "options": [{"type": "text", "value": "https://steamcommunity.com/tradeoffer/new/?partner=123456789&token=abcd1234"}]
            }
        )
        return resp.json()