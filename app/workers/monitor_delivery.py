from datetime import datetime, timedelta
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.db.models import Order, Task, TaskKind, DeliveryStatus


async def monitor_delivery(order_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        # TODO: раскомментировать когда будут ключи xPanda
        # from app.clients.xpanda import xpanda
        # resp = await xpanda.get_purchase(str(order.ggsel_order_id))
        # status = resp["status"]

        # Заглушка
        status = order.xpanda_status or "IN_PROGRESS"

        print(f"[MONITOR] Order {order_id} xpanda_status={status}")

        if status == "DONE":
            order.xpanda_status = "DONE"
            order.delivery_status = DeliveryStatus.done
            order.delivered_at = datetime.utcnow()

            # Создать MARK_DELIVERED
            task = Task(
                kind=TaskKind.MARK_DELIVERED,
                priority=1,
                payload={"order_id": order.id},
            )
            db.add(task)

            # Создать TRADE_WATCH через 7.5 дней
            watch_task = Task(
                kind=TaskKind.TRADE_WATCH,
                priority=20,
                payload={"order_id": order.id},
                scheduled_at=datetime.utcnow() + timedelta(days=7, hours=12),
            )
            db.add(watch_task)
            await db.commit()

        elif status == "ERROR":
            error_code = order.xpanda_error_code or "unknown"
            retry_codes = {"skins_unavailable", "trade_timeout",
                          "order was cancelled by creation timeout"}
            user_codes = {"invalid trade url", "user_cant_trade", "private_inventory"}

            if error_code in retry_codes and (order.xpanda_purchase_id is not None):
                # Ретрай через 5 минут
                task = Task(
                    kind=TaskKind.DELIVER,
                    priority=1,
                    payload={"order_id": order.id},
                    scheduled_at=datetime.utcnow() + timedelta(minutes=5),
                )
                db.add(task)
                await db.commit()

            elif error_code in user_codes:
                order.delivery_status = DeliveryStatus.needs_attention
                order.error_reason = error_code
                await db.commit()
                # TODO: отправить сообщение покупателю через ggsel chat

            else:
                order.delivery_status = DeliveryStatus.needs_attention
                order.error_reason = error_code
                await db.commit()

        else:
            # IN_PROGRESS или MONEY_BLOCKED — проверяем таймаут
            if order.paid_at and (datetime.utcnow() - order.paid_at).seconds > 2700:
                print(f"[MONITOR] Order {order_id} delivery timeout!")
                # TODO: алерт в Telegram

            # Перепланировать мониторинг через 30 сек
            task = Task(
                kind=TaskKind.MONITOR_DELIVERY,
                priority=20,
                payload={"order_id": order.id},
                scheduled_at=datetime.utcnow() + timedelta(seconds=30),
            )
            db.add(task)
            await db.commit()