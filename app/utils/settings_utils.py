from app.core.config import get_settings


def get_absolute_media_url(request, file_path: str):
    """
    Returns full URL based on environment.

    Development:
        http://localhost:8000/media/...

    Production:
        AWS S3 URL
    """

    if not file_path:
        return None

    settings = get_settings()

    # Production: S3 URL
    if settings.ENVIRONMENT == "production":
        return f"{settings.AWS_S3_BASE_URL}/{file_path}"

    # Development: Local Server
    return str(request.base_url) + file_path


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """
    Masks a secret value.

    Example:
    1234567890 -> 1234******
    abcd -> abcd****
    """
    if not value:
        return ""

    value = str(value)

    if len(value) <= visible_chars:
        return "*" * len(value)

    return value[:visible_chars] + "*" * (len(value) - visible_chars)
