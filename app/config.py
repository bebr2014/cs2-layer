from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    xpanda_api_key: str
    xpanda_hmac_secret: str

    ggsel_seller_id: str
    ggsel_api_key: str
    ggsel_so_username: str
    ggsel_so_password: str

    webhook_shared_secret: str

    database_url: str

    telegram_bot_token: str
    telegram_chat_id_critical: str
    telegram_chat_id_warn: str

    markup: float = 1.20
    min_price_rub: float = 100.0
    cs2_category_id: int = 0

    class Config:
        env_file = ".env"

settings = Settings()