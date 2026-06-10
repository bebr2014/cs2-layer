import hashlib
import hmac
import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, insert
from app.config import settings
from app.db import AsyncSessionLocal
from app.db.models import Offer, Order, Task, WebhookEvent, TaskKind, DeliveryStatus, WebhookKind

router = APIRouter()

TRADE_URL_RE = re.compile(
    r'^https://steamcommunity\.com/tradeoffer/new/\?partner=(\d+)&token=([A-Za-z0-9_-]{8})$'
)


def check_secret(secret: str):
    if not hmac.compare_digest(secret, settings.webhook_shared_secret):
        raise HTTPException(status_code=403, detail="Invalid secret")


@router.post("/hooks/ggsel/precheck/{offer_id}")
async def precheck(offer_id: int, request: Request, secret: str = ""):
    check_secret(secret)
    body = await request.json()
    print(f"[precheck] body: {body}", flush=True)

    product = body.get("product", {})
    options = body.get("options", [])
    id_i = body.get("id_i")

    # Найти оффер
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Offer).where(Offer.ggsel_offer_id == offer_id)
        )
        offer = result.scalar_one_or_none()

    if not offer:
        return {"error": "Оффер не найден"}

    # Проверить cnt
    if product.get("cnt") != 1:
        return {"error": "Количество должно быть 1"}

    # Найти trade URL в options
    trade_url = None
    for opt in options:
        if opt.get("type") == "text":
            trade_url = opt.get("value", "").strip()
            break

    if not trade_url:
        return {"error": "Укажите Steam Trade URL"}

    # Валидация формата
    match = TRADE_URL_RE.match(trade_url)
    if not match:
        return {"error": "Неверный формат Steam Trade URL"}

    partner = match.group(1)
    token = match.group(2)
    print(f"[precheck] offer_id={offer_id} trade_url={trade_url} partner={partner} token={token} id_i={id_i}", flush=True)

    # Проверить qty у xPanda
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Offer).where(Offer.market_hash_name == offer.market_hash_name)
        )
        offer_db = result.scalar_one_or_none()
        if offer_db and offer_db.xpanda_qty == 0:
            return {"error": "Товар временно недоступен"}

        # Сохранить trade URL если есть id_i
        if id_i is not None:
            result = await db.execute(
                select(Order).where(Order.ggsel_order_id == id_i)
            )
            order = result.scalar_one_or_none()
            if order:
                order.steam_trade_url = trade_url
                order.steam_partner = partner
                order.steam_token = token
            else:
                order = Order(
                    ggsel_order_id=id_i,
                    offer_id=offer.id,
                    market_hash_name=offer.market_hash_name,
                    steam_trade_url=trade_url,
                    steam_partner=partner,
                    steam_token=token,
                    xpanda_custom_id=str(id_i),
                )
                db.add(order)

        # Сохранить trade URL в WebhookEvent для последующего использования в notification
        precheck_ext_id = f"precheck-{offer_id}"
        result = await db.execute(
            select(WebhookEvent).where(WebhookEvent.external_id == precheck_ext_id)
        )
        existing_event = result.scalar_one_or_none()
        if existing_event:
            existing_event.payload = {"trade_url": trade_url, "partner": partner, "token": token}
            existing_event.processed_at = datetime.utcnow()
        else:
            db.add(WebhookEvent(
                kind=WebhookKind.precheck,
                external_id=precheck_ext_id,
                payload={"trade_url": trade_url, "partner": partner, "token": token},
                response_code=200,
            ))

        await db.commit()

    return {"error": None}


@router.post("/hooks/ggsel/notification/{offer_id}")
async def notification(offer_id: int, request: Request, secret: str = ""):
    check_secret(secret)
    body = await request.json()
    print(f"[notification] body: {body}", flush=True)

    id_i = body.get("id_i")
    id_d = body.get("id_d")
    amount = body.get("amount")
    email = body.get("email")
    ip = body.get("ip")
    date_str = body.get("date")

    async with AsyncSessionLocal() as db:
        # Идемпотентность
        existing = await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.kind == WebhookKind.notification,
                WebhookEvent.external_id == str(id_i)
            )
        )
        if existing.scalar_one_or_none():
            return {"status": "already processed"}

        # Найти оффер
        result = await db.execute(
            select(Offer).where(Offer.ggsel_offer_id == offer_id)
        )
        offer = result.scalar_one_or_none()
        if not offer:
            raise HTTPException(status_code=422, detail="Offer not found")

        # Взять trade URL из последнего precheck-события для этого оффера
        precheck_result = await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.kind == WebhookKind.precheck,
                WebhookEvent.external_id == f"precheck-{offer_id}",
            )
        )
        precheck_event = precheck_result.scalar_one_or_none()
        precheck_payload = precheck_event.payload if precheck_event else {}
        trade_url = precheck_payload.get("trade_url", "")
        partner = precheck_payload.get("partner", "")
        token = precheck_payload.get("token", "")

        # Сохранить заказ
        paid_at = datetime.fromisoformat(date_str) if date_str else datetime.utcnow()
        order = Order(
            ggsel_order_id=id_i,
            offer_id=offer.id,
            market_hash_name=offer.market_hash_name,
            amount_rub=amount,
            steam_trade_url=trade_url,
            steam_partner=partner,
            steam_token=token,
            buyer_email=email,
            buyer_ip=ip,
            xpanda_custom_id=str(id_i),
            delivery_status=DeliveryStatus.pending,
            paid_at=paid_at,
        )
        db.add(order)
        await db.flush()

        # Создать задачу DELIVER
        task = Task(
            kind=TaskKind.DELIVER,
            priority=1,
            payload={"order_id": order.id},
        )
        db.add(task)

        # Записать webhook event
        event = WebhookEvent(
            kind=WebhookKind.notification,
            external_id=str(id_i),
            payload=body,
            response_code=200,
        )
        db.add(event)

        await db.commit()

    return {"status": "ok"}
