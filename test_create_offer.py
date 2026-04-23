import asyncio
from datetime import datetime
from app.db import AsyncSessionLocal
from app.db.models import Offer, OfferStatus, Task, TaskKind, TaskStatus
from decimal import Decimal

async def main():
    async with AsyncSessionLocal() as db:
        # Проверим есть ли уже задача
        from sqlalchemy import select
        result = await db.execute(select(Task).where(Task.kind == TaskKind.CREATE_OFFER))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Task already exists: id={existing.id} status={existing.status}")
            # Сбросим в pending
            existing.status = TaskStatus.pending
            existing.scheduled_at = datetime.utcnow()
            await db.commit()
            print("Reset to pending")
        else:
            offer = Offer(
                market_hash_name="AK-47 | Redline (Field-Tested)",
                status=OfferStatus.pending_create,
                xpanda_price_usd=Decimal("10.000"),
                ggsel_price_rub=Decimal("1200.00"),
                xpanda_qty=1,
            )
            db.add(offer)
            await db.flush()
            task = Task(
                kind=TaskKind.CREATE_OFFER,
                priority=5,
                payload={"offer_id": offer.id},
                status=TaskStatus.pending,
                scheduled_at=datetime.utcnow(),
            )
            db.add(task)
            await db.commit()
            print(f"Created offer id={offer.id}, task created")

asyncio.run(main())