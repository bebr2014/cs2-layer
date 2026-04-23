import asyncio
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.db.models import Task, TaskStatus

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Task))
        tasks = result.scalars().all()
        for t in tasks:
            print(f"id={t.id} kind={t.kind} status={t.status}")
            print(f"  last_error={t.last_error}")
            print(f"  attempts={t.attempts}")

        # Сбросим в pending
        for t in tasks:
            if t.status == TaskStatus.failed:
                t.status = TaskStatus.pending
                t.attempts = 0
                t.last_error = None
        await db.commit()
        print("Reset done")

asyncio.run(main())