import base64
import re
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.db.models import Offer, OfferStatus
from app.clients.ggsel import ggsel_office
from app.config import settings

# Словарь износа EN → RU
WEAR_RU = {
    "Factory New": "Прямо с завода",
    "Minimal Wear": "Минимальный износ",
    "Field-Tested": "Немного поношенное",
    "Well-Worn": "Поношенное",
    "Battle-Scarred": "Закалённое в боях",
}

# Дефолтная обложка — 1x1 белый PNG base64
DEFAULT_COVER_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


def parse_wear(market_hash_name: str) -> str | None:
    for wear_en in WEAR_RU:
        if wear_en in market_hash_name:
            return wear_en
    return None


def build_titles(market_hash_name: str) -> tuple[str, str]:
    title_en = market_hash_name
    wear_en = parse_wear(market_hash_name)
    if wear_en:
        title_ru = market_hash_name.replace(f"({wear_en})", f"| {WEAR_RU[wear_en]}").strip()
    else:
        title_ru = market_hash_name
    return title_en, title_ru


def build_description(market_hash_name: str) -> tuple[str, str]:
    wear_en = parse_wear(market_hash_name) or ""
    wear_ru = WEAR_RU.get(wear_en, "")

    # Детектируем спецпрефиксы
    prefix = ""
    if "★" in market_hash_name:
        prefix = "Нож / Перчатки"
    elif "StatTrak™" in market_hash_name:
        prefix = "StatTrak™ — счётчик убийств"
    elif "Souvenir" in market_hash_name:
        prefix = "Сувенирный предмет"

    desc_ru = f"""CS2 скин | {market_hash_name}
{f"Тип: {prefix}" if prefix else ""}
Wear: {wear_en} {f"({wear_ru})" if wear_ru else ""}

Предмет передаётся через Steam трейд на ваш Steam аккаунт.
Автоматическая выдача после оплаты.

Как получить Trade URL:
1. Steam → Инвентарь → Обмен
2. Скопируйте ссылку на обмен
3. Вставьте её в поле "Ваш Steam Trade URL" перед оплатой""".strip()

    desc_en = f"""CS2 skin | {market_hash_name}
{f"Type: {prefix}" if prefix else ""}
Wear: {wear_en}

Item is delivered via Steam trade to your Steam account.
Automatic delivery after payment.

How to get Trade URL:
1. Steam → Inventory → Trade Offers → Privacy
2. Copy your trade offer URL
3. Paste it into "Your Steam Trade URL" field before payment""".strip()

    return desc_ru, desc_en


async def create_offer(offer_id: int) -> None:
    """
    Полная 7-шаговая цепочка создания оффера на ggsel.
    Каждый шаг идемпотентен — при ретрае продолжаем с того же места.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Offer).where(Offer.id == offer_id))
        offer = result.scalar_one_or_none()
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")

        market_hash_name = offer.market_hash_name
        price_rub = float(offer.ggsel_price_rub or 100)
        title_en, title_ru = build_titles(market_hash_name)
        desc_ru, desc_en = build_description(market_hash_name)

        try:
            # Шаг 1: Создать draft (если ещё нет)
            if not offer.ggsel_offer_id:
                data = await ggsel_office.create_draft(
                    title_ru=title_ru,
                    title_en=title_en,
                    description_ru=desc_ru,
                    description_en=desc_en,
                    category_id=settings.cs2_category_id,
                    cover_base64=DEFAULT_COVER_B64,
                )
                offer.ggsel_offer_id = data["data"]["id"]
                offer.ggsel_id_goods = data["data"].get("ggsel_id")
                offer.status = OfferStatus.draft
                await db.commit()

            ggsel_id = offer.ggsel_offer_id

            # Шаг 2: Цена + unlimited_quantity
            await ggsel_office.update_price(ggsel_id, price_rub)

            # Шаг 3: Создать опцию Steam Trade URL (если ещё нет)
            if not offer.ggsel_option_id:
                opt_data = await ggsel_office.create_option(ggsel_id)
                offer.ggsel_option_id = opt_data["data"]["id"]
                await db.commit()

            # Шаг 4: delivery_kind = manual
            await ggsel_office.set_delivery_kind(ggsel_id)

            # Шаг 5: precheck settings
            await ggsel_office.set_precheck(ggsel_id, offer.ggsel_option_id)

            # Шаг 6: notification
            await ggsel_office.set_notification(ggsel_id)

            # Шаг 7: активировать
            await ggsel_office.activate_offer(ggsel_id)

            offer.status = OfferStatus.active
            offer.error_count = 0
            await db.commit()

        except Exception as e:
            offer.error_count = (offer.error_count or 0) + 1
            offer.last_error = str(e)
            if offer.error_count >= 5:
                offer.status = OfferStatus.error
            await db.commit()
            raise