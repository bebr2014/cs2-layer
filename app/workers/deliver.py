import asyncio
from datetime import datetime
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.db.models import Order, Offer, Task, TaskKind, DeliveryStatus


async def deliver_order(order_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        result2 = await db.execute(select(Offer).where(Offer.id == order.offer_id))
        offer = result2.scalar_one_or_none()

        # max_price = xpanda_price + 10% запас
        max_price_cents = int(float(offer.xpanda_price_usd or 10) * 1.10 * 1000)

        from app.clients.xpanda import xpanda
        resp = await xpanda.create_purchase(
            product=order.market_hash_name,
            partner=order.steam_partner,
            token=order.steam_token,
            max_price=max_price_cents,
            custom_id=str(order.ggsel_order_id),
        )

        order.xpanda_purchase_id = resp["id"]
        order.xpanda_status = resp["status"]  # MONEY_BLOCKED
        order.max_price_cents = max_price_cents
        order.delivery_status = DeliveryStatus.dispatched

        # Создать задачу мониторинга
        task = Task(
            kind=TaskKind.MONITOR_DELIVERY,
            priority=20,
            payload={"order_id": order.id},
            scheduled_at=datetime.utcnow().__class__.utcnow(),
        )
        db.add(task)
        await db.commit()