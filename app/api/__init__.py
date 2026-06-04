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

@app.get("/fix-precheck-urls")
async def fix_precheck_urls():
    from app.db import AsyncSessionLocal
    from app.db.models import Offer
    from app.clients.ggsel import ggsel_office
    from app.config import settings
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Offer).where(Offer.ggsel_offer_id.isnot(None)))
        offers = result.scalars().all()
        updated = 0
        errors = []
        for offer in offers:
            gid = offer.ggsel_offer_id
            precheck_url = f"https://cs2-layer-production.up.railway.app/hooks/ggsel/precheck/{gid}?secret={settings.webhook_shared_secret}"
            notification_url = f"https://cs2-layer-production.up.railway.app/hooks/ggsel/notification/{gid}?secret={settings.webhook_shared_secret}"
            try:
                await ggsel_office.patch_offer(gid, precheck_url, notification_url)
                updated += 1
            except Exception as e:
                errors.append({"ggsel_offer_id": gid, "error": str(e)})
        return {"updated": updated, "errors": errors}

@app.get("/fix-options")
async def fix_options():
    from app.db import AsyncSessionLocal
    from app.db.models import Offer, OfferStatus
    from app.clients.ggsel import ggsel_office
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Offer).where(
                Offer.ggsel_offer_id.isnot(None),
                Offer.status == OfferStatus.active,
            )
        )
        offers = result.scalars().all()
        updated = 0
        errors = []
        for offer in offers:
            try:
                await ggsel_office.create_option(offer.ggsel_offer_id)
                updated += 1
            except Exception as e:
                errors.append({"ggsel_offer_id": offer.ggsel_offer_id, "error": str(e)})
        return {"updated": updated, "errors": errors}

@app.get("/create-ak47-tasks")
async def create_ak47_tasks():
    from app.db import AsyncSessionLocal
    from app.db.models import Offer, OfferStatus, Task, TaskKind
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Offer).where(
                Offer.market_hash_name.contains("AK-47"),
                Offer.status == OfferStatus.pending_create,
            )
        )
        offers = result.scalars().all()
        for offer in offers:
            db.add(Task(kind=TaskKind.CREATE_OFFER, payload={"offer_id": offer.id}))
        await db.commit()
        return {"created": len(offers), "offer_ids": [o.id for o in offers]}