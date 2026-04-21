import hashlib
import hmac
import httpx
from app.config import settings


BASE_URL = "https://xpanda.gg/v1"  # уточнить реальный URL


class XPandaClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Token {settings.xpanda_api_key}",
            "Content-Type": "application/json",
        }

    def _sign(self, market_hash_name: str, partner: str, token: str,
              max_price: int, custom_id: str) -> str:
        # ФОРМАТ ПОДПИСИ — ЗАГЛУШКА, уточнить у xPanda
        msg = f"{market_hash_name}|{partner}|{token}|{max_price}|{custom_id}"
        return hmac.new(
            settings.xpanda_hmac_secret.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()

    async def get_prices(self, names: list[str] = None) -> dict:
        """
        Получить прайс xPanda.
        Без names[] — весь каталог (или 100, выясним эмпирически).
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=10) as client:
            params = {}
            if names:
                params = [("names[]", n) for n in names]
            resp = await client.get(f"{BASE_URL}/items/prices/", params=params)
            resp.raise_for_status()
            return resp.json()

    async def create_purchase(
        self,
        market_hash_name: str,
        partner: str,
        token: str,
        max_price: int,
        custom_id: str,
    ) -> dict:
        """
        POST /v1/purchases/ — заказать скин у xPanda.
        """
        sign = self._sign(market_hash_name, partner, token, max_price, custom_id)
        payload = {
            "product": market_hash_name,
            "partner": partner,
            "token": token,
            "max_price": max_price,
            "custom_id": custom_id,
            "sign": sign,
        }
        async with httpx.AsyncClient(headers=self.headers, timeout=10) as client:
            resp = await client.post(f"{BASE_URL}/purchases/", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_purchase(self, custom_id: str) -> dict:
        """
        GET /v1/purchases/?custom_id=... — проверить статус заказа.
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/purchases/",
                params={"custom_id": custom_id}
            )
            resp.raise_for_status()
            return resp.json()


xpanda = XPandaClient()