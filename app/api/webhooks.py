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

    product = body.get("product", {})
    options = body.get("options", [])

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

    # Проверить qty у xPanda
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Offer).where(Offer.market_hash_name == offer.market_hash_name)
        )
        offer_db = result.scalar_one_or_none()
        if offer_db and offer_db.xpanda_qty == 0:
            return {"error": "Товар временно недоступен"}

    return {"error": None}


@router.post("/hooks/ggsel/notification/{offer_id}")
async def notification(offer_id: int, request: Request, secret: str = ""):
    check_secret(secret)
    body = await request.json()

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

        # Получить trade URL из ggsel order
        # TODO: заменить на реальный вызов ggsel_office.get_order(id_i)
        # order_data = await ggsel_office.get_order(id_i)
        # trade_url = extract_trade_url(order_data)
        trade_url = ""  # заглушка
        partner = ""
        token = ""

        match = TRADE_URL_RE.match(trade_url) if trade_url else None
        if match:
            partner = match.group(1)
            token = match.group(2)

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
@app.get("/test-precheck")
async def test_precheck():
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://cs2-layer-production.up.railway.app/hooks/ggsel/precheck/1?secret={settings.webhook_shared_secret}",
            json={
                "product": {"cnt": 1},
                "options": [{"type": "text", "value": "https://steamcommunity.com/tradeoffer/new/?partner=123456789&token=abcd1234"}]
            }
        )
        return resp.json()