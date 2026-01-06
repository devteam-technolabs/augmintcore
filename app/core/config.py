from typing import List, Optional

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "AugmintCore"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Database ---
    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    DB_ECHO: bool = False

    # --- Security ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 300  # 30 hours

    # --- CORS ---
    CORS_ORIGINS: List[str] = Field(default_factory=list)
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # --- SMTP (Email) ---
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    # --- Tokens & Stripe ---
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days
    REFRESH_SECRET_KEY: str
    ACCESS_SECRET_KEY: str
    STRIPE_SECRET_KEY: str
    PRICE_ID_YEARLY: dict 
    PRICE_ID_MONTHLY: dict 
    STRIPE_WEBHOOK_SECRET: str  

    # --- KMS / AWS ---
    KMS_KEY_ID: str 
    AWS_REGION: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str

    # --- Crypto / Market APIs (Old) ---
    COINGECKO_MARKETS_URL: str
    COINBASE_REST_URL: str
    COINBASE_CANDLES_PATH: str
    COINBASE_WS_URL: str
    DEFAULT_VS_CURRENCY: str = "usd"

    # --- Coinbase API Settings (Old/New Shared) ---
    COINBASE_API_KEY_ENC: str
    COINBASE_API_SECRET_ENC: str
    COINBASE_API_PASSPHRASE_ENC: str
    COINBASE_EXCHANGE_SANDBOX: bool = False

    # --- CoinMarketCap APIs (New) ---
    CMC_DETAIL_URL: str = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail"
    CMC_LISTING_URL: str = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"

    # --- Dashboard Configuration (New) ---
    TIMEFRAME_MAP: dict = {
        "1S": 60,
        "1H": 60,
        "1D": 300,
        "1W": 3600,
        "1M": 21600,
        "1Y": 86400,
    }


def get_settings() -> AppSettings:
    return AppSettings()
