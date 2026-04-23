from datetime import datetime, timedelta
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.db.models import Order, DeliveryStatus


async def trade_watch(order_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order.delivery_status == DeliveryStatus.finalized:
            print(f"[TRADE_WATCH] Order {order_id} already finalized")
            return

        if not order.delivered_at:
            print(f"[TRADE_WATCH] Order {order_id} no delivered_at")
            return

        days_since = (datetime.utcnow() - order.delivered_at.replace(tzinfo=None)).days

        if days_since >= 7:
            order.delivery_status = DeliveryStatus.finalized
            await db.commit()
            print(f"[TRADE_WATCH] Order {order_id} finalized after 7 days")
            return

        # TODO: раскомментировать когда будут ключи xPanda
        # from app.clients.xpanda import xpanda
        # resp = await xpanda.get_purchase(str(order.ggsel_order_id))
        # if resp["status"] == "ERROR":
        #     order.delivery_status = DeliveryStatus.needs_attention
        #     order.error_reason = "trade_protection_reverted"
        #     await db.commit()
        #     # TODO: critical alert telegram

        print(f"[TRADE_WATCH] Order {order_id} ok, {7 - days_since} days left")