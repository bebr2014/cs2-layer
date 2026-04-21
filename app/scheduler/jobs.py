import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db import AsyncSessionLocal
from app.db.models import Offer, OfferStatus, Task, TaskKind


async def xpanda_sync():
    """
    Каждые 10 мин — синхронизация цен и остатков с xPanda.
    TODO: заменить заглушку на реальный вызов xpanda.get_prices()
    """
    print(f"[Scheduler] xpanda_sync started at {datetime.utcnow()}")

    # TODO: раскомментировать когда будут credentials xPanda
    # from app.clients.xpanda import xpanda
    # snapshot = await xpanda.get_prices()

    # Заглушка — пропускаем до получения xPanda credentials
    print("[Scheduler] xpanda_sync: xPanda client not configured yet, skipping")


async def reconcile():
    """Каждый час — сверка заказов с ggsel."""
    print(f"[Scheduler] reconcile started at {datetime.utcnow()}")

    # TODO:
    # from app.clients.ggsel import ggsel_seller
    # sales = await ggsel_seller.get_last_sales(top=100)
    # for sale in sales: ...
    print("[Scheduler] reconcile: not implemented yet")


async def trade_protection():
    """Каждый час — проверка 7-дневного окна после доставки."""
    print(f"[Scheduler] trade_protection started at {datetime.utcnow()}")

    # TODO: проверить orders где delivery_status='done' и delivered_at < 7 дней
    print("[Scheduler] trade_protection: not implemented yet")


async def token_refresh():
    """Каждые 20 мин — обновление токенов ggsel."""
    print(f"[Scheduler] token_refresh started at {datetime.utcnow()}")

    # TODO: обновить токены через GgselToken в БД
    print("[Scheduler] token_refresh: not implemented yet")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(xpanda_sync, "interval", minutes=10, id="xpanda_sync")
    scheduler.add_job(reconcile, "interval", hours=1, id="reconcile")
    scheduler.add_job(trade_protection, "interval", hours=1, id="trade_protection")
    scheduler.add_job(token_refresh, "interval", minutes=20, id="token_refresh")

    scheduler.start()
    print("[Scheduler] Started")
    return scheduler