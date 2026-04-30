import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db import AsyncSessionLocal
from app.db.models import Offer, OfferStatus, Task, TaskKind


async def xpanda_sync():
    print(f"[Scheduler] xpanda_sync started at {datetime.utcnow()}")
    try:
        from app.fx import get_usd_rub
        fx_rate = await get_usd_rub()
        print(f"[Scheduler] FX rate: {fx_rate}")
    except Exception as e:
        from app.alerts import warn
        await warn(f"fx_rate_stale: {e}")
        return

    from app.clients.xpanda import xpanda
    from app.config import settings
    try:
        snapshot = await xpanda.get_prices()
        items = snapshot.get("items", [])
        print(f"[Scheduler] Got {len(items)} items from xPanda")
    except Exception as e:
        from app.alerts import warn
        await warn(f"xpanda_sync_failed: {e}")
        return

    async with AsyncSessionLocal() as db:
        updated = 0
        created = 0
        for item in items:
            name = item.get("market_hash_name") or item.get("name")
            price_usd = item.get("price")
            qty = item.get("quantity", 1)
            if not name or not price_usd:
                continue

            price_rub = round(float(price_usd) * fx_rate * settings.markup, 2)
            if price_rub < settings.min_price_rub:
                continue

            result = await db.execute(select(Offer).where(Offer.market_hash_name == name))
            offer = result.scalar_one_or_none()

            if offer:
                offer.xpanda_price_usd = price_usd
                offer.ggsel_price_rub = price_rub
                offer.xpanda_qty = qty
                offer.last_synced_at = datetime.utcnow()
                updated += 1
            else:
                offer = Offer(
                    market_hash_name=name,
                    xpanda_price_usd=price_usd,
                    ggsel_price_rub=price_rub,
                    xpanda_qty=qty,
                    last_synced_at=datetime.utcnow(),
                )
                db.add(offer)
                created += 1

        await db.commit()
        print(f"[Scheduler] xpanda_sync done: {created} created, {updated} updated")

async def reconcile():
    print(f"[Scheduler] reconcile started at {datetime.utcnow()}")
    from app.workers.reconciler import reconcile as do_reconcile
    await do_reconcile()

async def token_refresh():
    print(f"[Scheduler] token_refresh started at {datetime.utcnow()}")
    try:
        from app.clients.ggsel import ggsel_seller, ggsel_office
        await ggsel_seller._get_token()
        await ggsel_office._get_token()
        print("[Scheduler] token_refresh: OK")
    except Exception as e:
        from app.alerts import critical
        await critical(f"token_refresh_failed: {e}")


async def trade_protection():
    """Каждый час — проверка 7-дневного окна после доставки."""
    print(f"[Scheduler] trade_protection started at {datetime.utcnow()}")

    # TODO: проверить orders где delivery_status='done' и delivered_at < 7 дней
    print("[Scheduler] trade_protection: not implemented yet")



def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(xpanda_sync, "interval", minutes=10, id="xpanda_sync")
    scheduler.add_job(reconcile, "interval", hours=1, id="reconcile")
    scheduler.add_job(trade_protection, "interval", hours=1, id="trade_protection")
    scheduler.add_job(token_refresh, "interval", minutes=20, id="token_refresh")

    scheduler.start()
    print("[Scheduler] Started")
    return scheduler