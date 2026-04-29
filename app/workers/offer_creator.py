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

DEFAULT_COVER_B64 = "iVBORw0KGgoAAAANSUhEUgAAAfQAAAH0CAIAAABEtEjdAAAJzElEQVR4nO3aX6jfZR3A8c/cLKcJ1dKk2FHoD5aSIkmhwVpYK9KLQmxd2B8jKwy7MQghKuiyoETCi/4sKGTuIugPMa1MF1FQzSihBAmnYWhkaDlTz9aFx41tJ/LCnTPee72uft/n93y/z/O9eZ+Hc86ahYWFAaDlhNXeAADPP3EHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4AgcQcIEneAIHEHCBJ3gCBxBwgSd4Agdau9geXdd+2e1d4CwHN15g0Lq72Fwzm5AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEifuKesNH58rfzfvumPf+aE7duDT48gvm8lvnitvn8tuWBs+9arbumg/cNWe945Dbj5z5yX8ufXXqxrly95xyxsGRT+2dK24/eO+BceD4IO4r5cy3z9nvn5svnu2bZveN885tS+Nbvjk7r5pbNs/vb5pNX5r1p805H5ztm+aHW2fzVw95wmEzD1h30rz75vnJJ+bffzs4uPifOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPkovAxwrBP3lbJm7fLjd2+bba+fv/5iNn9lLvr80uCLXzUXfnru/Mz/mbn2BXP+NTNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPgovAxwrBP3lbJm7fLjd2+bba+fv/5iNn9lLvr80uCLXzUXfnru/Mz/mbn2BXP+NTNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPifOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPifOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPivOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPivOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPifOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPivOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPifOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55wmEzD7jkprl72zz4q8NX/OXn5qIvzPZNR/GlgGOVk/tKedk589Dug5e3XT37npqZ2XX9bN01W74xr3zLPLBr/vGnuWfHzMxrL597f3DIEw6b+YwLrp3FJ+YPX19mxT0/m5nZuPifOWHdbHzr0X4t4Ni0brU3cNx443Wz6/p5eu/MzF9+PK9+z5xw4ux7ak4+fdaeNDNz7/dn70OzfsPsvnH275vH7p/1Gw55IkjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIEjcAYLEHSBI3AGCxB0gSNwBgsQdIGjNwsLCau8BgOeZkztAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBIk7QJC4AwSJO0CQuAMEiTtAkLgDBP0HWa3XYr5qmfkAAAAASUVORK5CYII="


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
    return "CS2 skin", "CS2 skin"



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