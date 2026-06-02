import hashlib
import time
import httpx
from app.config import settings

SELLER_API_URL = "https://seller.ggsel.com/api_sellers/api"
SELLER_OFFICE_V2_URL = "https://back-office.ggselstg.org/api_sellers/v2"


class GgselSellerAPIClient:
    """Публичный Seller API v1 — bulk price update, purchase info, chat."""

    def __init__(self):
        self._token: str | None = None

    async def _get_token(self) -> str:
        ts = int(time.time())
        sign = hashlib.sha256(
            f"{settings.ggsel_api_key}{ts}".encode()
        ).hexdigest()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SELLER_API_URL}/apilogin",
                json={
                    "seller_id": int(settings.ggsel_seller_id),
                    "timestamp": ts,
                    "sign": sign,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["token"]
            return self._token

    async def update_prices(self, items: list[dict]) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{SELLER_API_URL}/product/edit/prices",
                params={"token": token},
                json=items,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_task_status(self, task_id: str) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SELLER_API_URL}/product/edit/UpdateProductsTaskStatus",
                params={"token": token, "taskId": task_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_last_sales(self, top: int = 100) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{SELLER_API_URL}/seller-last-sales",
                params={"token": token, "top": top},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_chat(self, order_id: int, message: str) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SELLER_API_URL}/debates/v2",
                params={"token": token, "id_i": order_id},
                json={"message": message},
            )
            resp.raise_for_status()
            return resp.json()


class GgselSellerOfficeClient:
    """Seller Office API v2 — создание офферов, управление, доставка."""

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": settings.ggsel_api_key,
        }

    async def create_offer(
        self,
        title_ru: str,
        title_en: str,
        description_ru: str,
        description_en: str,
        category_id: int,
        cover_base64: str,
        price: float,
        precheck_url: str,
        notification_url: str,
    ) -> dict:
        body = {
            "title_ru": title_ru,
            "title_en": title_en,
            "description_ru": description_ru,
            "description_en": description_en,
            "cover_image_ru": cover_base64,
            "price": price,
            "currency": "RUB",
            "is_autoselling": False,
            "category_id": category_id,
            "delivery": "manual",
            "pre_payment_settings": {
                "is_enabled": True,
                "url": precheck_url,
                "allow_payment": False,
            },
            "notification_settings": {
                "type": "url",
                "url": notification_url,
                "http_method": "POST",
                "is_disabled": False,
                "is_default": False,
            },
        }
        async with httpx.AsyncClient(headers=self._headers(), timeout=30) as client:
            resp = await client.post(f"{SELLER_OFFICE_V2_URL}/offers", json=body)
            resp.raise_for_status()
            return resp.json()

    async def update_price(self, offer_id: int, price: float) -> dict:
        async with httpx.AsyncClient(headers=self._headers(), timeout=30) as client:
            resp = await client.patch(
                f"{SELLER_OFFICE_V2_URL}/offers/{offer_id}",
                json={"price": price},
            )
            resp.raise_for_status()
            return resp.json()

    async def activate_offer(self, offer_id: int) -> dict:
        async with httpx.AsyncClient(headers=self._headers(), timeout=10) as client:
            resp = await client.post(f"{SELLER_OFFICE_V2_URL}/offers/{offer_id}/activate")
            resp.raise_for_status()
            return resp.json()

    async def pause_offers(self, offer_ids: list[int]) -> dict:
        async with httpx.AsyncClient(headers=self._headers(), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_V2_URL}/offers/batch/actions/pause",
                json={"offer_ids": offer_ids},
            )
            resp.raise_for_status()
            return resp.json()

    async def activate_offers(self, offer_ids: list[int]) -> dict:
        async with httpx.AsyncClient(headers=self._headers(), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_V2_URL}/offers/batch/actions/activate",
                json={"offer_ids": offer_ids},
            )
            resp.raise_for_status()
            return resp.json()

    async def mark_delivered(self, order_id: int) -> dict:
        async with httpx.AsyncClient(headers=self._headers(), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_V2_URL}/orders/{order_id}/deliveries/delivered"
            )
            resp.raise_for_status()
            return resp.json()

    async def get_order(self, order_id: int) -> dict:
        async with httpx.AsyncClient(
            headers={**self._headers(), "currency": "RUB"}, timeout=10
        ) as client:
            resp = await client.get(f"{SELLER_OFFICE_V2_URL}/orders/{order_id}")
            resp.raise_for_status()
            return resp.json()


ggsel_seller = GgselSellerAPIClient()
ggsel_office = GgselSellerOfficeClient()
