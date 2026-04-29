import hashlib
import time
import httpx
from app.config import settings

SELLER_API_URL = "https://seller.ggsel.com/api_sellers/api"
SELLER_OFFICE_URL = "https://seller.ggsel.com/api/v1"


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
    """Seller Office API — создание офферов, управление, доставка."""

    def __init__(self):
        self._access_token: str | None = None

    async def _get_token(self) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://seller.ggsel.com/api/auth/login",
                headers={"locale": "ru"},
                json={
                    "email": settings.ggsel_so_username,
                    "password": settings.ggsel_so_password,
                }
            )
            resp.raise_for_status()
            token = resp.cookies.get("ACCESS_TOKEN")
            if not token:
                raise ValueError("No ACCESS_TOKEN in cookies")
            self._access_token = token
            self._cookies = dict(resp.cookies)
            return token

    def _headers(self, token: str) -> dict:
        return {
            "Content-Type": "application/json",
            "locale": "ru",
            "Cookie": f"ACCESS_TOKEN={token}; user-role=seller",
        }

    async def create_draft(self, title_ru, title_en, description_ru, description_en, category_id, cover_base64):
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=30, cookies=self._cookies) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_URL}/offers/draft",
                headers={"locale": "ru", "Content-Type": "application/json"},
                json={"offer": {
                    "title_ru": title_ru,
                    "title_en": title_en,
                    "description_ru": description_ru,
                    "description_en": description_en,
                    "category_id": category_id,
                    "autoselling": False,
                    "delivery_kind": "auto",
                    "check_unique_code_url": None,
                    "cover_image_attributes": {
                        "attachment_data_uri": f"data:image/png;base64,{cover_base64}"
                    }
                }}
            )
            print(f"[CREATE_DRAFT] status={resp.status_code} body={resp.text[:500]}")
            resp.raise_for_status()
            return resp.json()

    async def update_price(self, offer_id: int, price: float) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(headers=self._headers(token), timeout=30) as client:
            resp = await client.patch(
                f"{SELLER_OFFICE_URL}/offers/{offer_id}/update_price",
                json={"offer": {"price": price, "unlimited_quantity": True}}
            )
            resp.raise_for_status()
            return resp.json()

    async def create_option(self, offer_id: int) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_URL}/offers/{offer_id}/options",
                json={"option": {
                    "title_ru": "Ваш Steam Trade URL",
                    "title_en": "Your Steam Trade URL",
                    "comment_ru": "Ссылка вида https://steamcommunity.com/tradeoffer/new/?partner=...&token=...",
                    "required": True,
                    "kind": "text",
                    "position": 1,
                }}
            )
            resp.raise_for_status()
            return resp.json()

    async def set_delivery_kind(self, offer_id: int) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.put(
                f"{SELLER_OFFICE_URL}/offers/{offer_id}",
                json={"offer": {"delivery_kind": "manual"}}
            )
            resp.raise_for_status()
            return resp.json()

    async def set_precheck(self, offer_id: int, option_id: int) -> dict:
        token = await self._get_token()
        url = f"https://cs2-layer-production.up.railway.app/hooks/ggsel/precheck/{offer_id}?secret={settings.webhook_shared_secret}"
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.put(
                f"{SELLER_OFFICE_URL}/offers/{offer_id}/update_precheck_settings",
                json={"offer": {
                    "enabled": True,
                    "url": url,
                    "allow_payment": False,
                    "show_option_ids": [option_id],
                }}
            )
            resp.raise_for_status()
            return resp.json()

    async def set_notification(self, offer_id: int) -> dict:
        token = await self._get_token()
        url = f"https://cs2-layer-production.up.railway.app/hooks/ggsel/notification/{offer_id}?secret={settings.webhook_shared_secret}"
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.patch(
                f"{SELLER_OFFICE_URL}/offers/{offer_id}/update_notification",
                json={"notification": {
                    "kind": "url",
                    "url": url,
                    "method": "post",
                    "default": False,
                    "disabled": False,
                }}
            )
            resp.raise_for_status()
            return resp.json()

    async def activate_offer(self, offer_id: int) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_URL}/offers/{offer_id}/activate"
            )
            resp.raise_for_status()
            return resp.json()

    async def pause_offers(self, offer_ids: list[int]) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_URL}/offers/batch/actions/pause",
                json={"offer_ids": offer_ids}
            )
            resp.raise_for_status()
            return resp.json()

    async def activate_offers(self, offer_ids: list[int]) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_URL}/offers/batch/actions/activate",
                json={"offer_ids": offer_ids}
            )
            resp.raise_for_status()
            return resp.json()

    async def mark_delivered(self, order_id: int) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(headers=self._headers(token), timeout=10) as client:
            resp = await client.post(
                f"{SELLER_OFFICE_URL}/orders/{order_id}/deliveries/delivered"
            )
            resp.raise_for_status()
            return resp.json()

    async def get_order(self, order_id: int) -> dict:
        token = await self._get_token()
        headers = {**self._headers(token), "currency": "RUB"}
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            resp = await client.get(
                f"{SELLER_OFFICE_URL}/orders/{order_id}"
            )
            resp.raise_for_status()
            return resp.json()


ggsel_seller = GgselSellerAPIClient()
ggsel_office = GgselSellerOfficeClient()


