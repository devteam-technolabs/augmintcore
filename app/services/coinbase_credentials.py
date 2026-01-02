from app.core.config import get_settings
from app.security.kms_service import kms_service

settings = get_settings()


async def get_coinbase_credentials():
    """
    Decrypt Coinbase credentials safely at runtime.
    Returns None if not configured.
    """

    if not settings.COINBASE_API_KEY_ENC:
        return None

    return {
        "apiKey": await kms_service.decrypt(settings.COINBASE_API_KEY_ENC),
        "secret": await kms_service.decrypt(settings.COINBASE_API_SECRET_ENC),
        "passphrase": await kms_service.decrypt(
            settings.COINBASE_API_PASSPHRASE_ENC
        ),
        "sandbox": settings.COINBASE_EXCHANGE_SANDBOX,
    }
