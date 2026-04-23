from datetime import datetime
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.db.models import Order, Task, TaskKind, DeliveryStatus
from app.clients.ggsel import ggsel_seller


async def reconcile() -> None:
    print(f"[RECONCILER] Started at {datetime.utcnow()}")

    async with AsyncSessionLocal() as db:
        try:
            sales = await ggsel_seller.get_last_sales(top=100)
            items = sales.get("sales", []) or sales.get("data", []) or []
            print(f"[RECONCILER] Got {len(items)} sales from ggsel")
        except Exception as e:
            print(f"[RECONCILER] Failed to get sales: {e}")
            return

        for sale in items:
            invoice_id = sale.get("id_i") or sale.get("invoice_id")
            if not invoice_id:
                continue

            result = await db.execute(
                select(Order).where(Order.ggsel_order_id == invoice_id)
            )
            order = result.scalar_one_or_none()

            if not order:
                print(f"[RECONCILER] Missing order {invoice_id} — webhook lost, backfill needed")
                # TODO: backfill через get_order + создать DELIVER задачу
                continue

            # Проверяем статус
            invoice_state = sale.get("invoice_state")
            if invoice_state in (2, 5):
                if order.delivery_status != DeliveryStatus.failed:
                    print(f"[RECONCILER] Refund detected for order {invoice_id}")
                    # TODO: алерт в Telegram

    print(f"[RECONCILER] Done")