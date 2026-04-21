import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, update
from app.db import AsyncSessionLocal
from app.db.models import Task, TaskKind, TaskStatus

WORKER_ID = str(uuid.uuid4())


async def pop_task(db) -> Task | None:
    """Взять следующую задачу из очереди (SKIP LOCKED)."""
    result = await db.execute(
        select(Task)
        .where(
            Task.status == TaskStatus.pending,
            Task.scheduled_at <= datetime.utcnow(),
        )
        .order_by(Task.priority.asc(), Task.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return result.scalar_one_or_none()


async def handle_task(task: Task) -> None:
    """Роутер — запускает нужный воркер по типу задачи."""
    from app.workers.offer_creator import create_offer

    payload = task.payload or {}

    match task.kind:
        case TaskKind.CREATE_OFFER:
            await create_offer(payload["offer_id"])

        case TaskKind.DELIVER:
            # TODO: await deliver_order(payload["order_id"])
            pass

        case TaskKind.MONITOR_DELIVERY:
            # TODO: await monitor_delivery(payload["order_id"])
            pass

        case TaskKind.MARK_DELIVERED:
            # TODO: await mark_delivered(payload["order_id"])
            pass

        case TaskKind.UPDATE_PRICE_BATCH:
            # TODO: await update_price_batch(payload["offer_ids"])
            pass

        case TaskKind.TOGGLE_STATUS_BATCH:
            # TODO: await toggle_status_batch(payload)
            pass

        case TaskKind.TRADE_WATCH:
            # TODO: await trade_watch(payload["order_id"])
            pass

        case _:
            raise ValueError(f"Unknown task kind: {task.kind}")


async def run_worker() -> None:
    """Основной цикл воркера."""
    print(f"[Worker] Started, id={WORKER_ID}")

    while True:
        try:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    task = await pop_task(db)

                    if not task:
                        await asyncio.sleep(1)
                        continue

                    # Берём задачу в работу
                    task.status = TaskStatus.processing
                    task.locked_by = WORKER_ID
                    task.locked_at = datetime.utcnow()
                    task.attempts += 1

                try:
                    await handle_task(task)

                    async with AsyncSessionLocal() as db2:
                        async with db2.begin():
                            result = await db2.execute(
                                select(Task).where(Task.id == task.id)
                            )
                            t = result.scalar_one()
                            t.status = TaskStatus.done
                            t.updated_at = datetime.utcnow()

                    print(f"[Worker] Task {task.id} ({task.kind}) done")

                except Exception as e:
                    print(f"[Worker] Task {task.id} ({task.kind}) failed: {e}")

                    async with AsyncSessionLocal() as db2:
                        async with db2.begin():
                            result = await db2.execute(
                                select(Task).where(Task.id == task.id)
                            )
                            t = result.scalar_one()
                            t.last_error = str(e)

                            if t.attempts >= t.max_attempts:
                                t.status = TaskStatus.failed
                            else:
                                # Backoff: 2, 5, 15, 30 мин
                                delays = [2, 5, 15, 30]
                                delay = delays[min(t.attempts - 1, len(delays) - 1)]
                                t.status = TaskStatus.pending
                                t.scheduled_at = datetime.utcnow() + timedelta(minutes=delay)

        except Exception as e:
            print(f"[Worker] Loop error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_worker())