from datetime import datetime, timedelta

from jose import jwt

from app.core.config import get_settings

settings = get_settings()


def create_access_token(data: dict, minutes: int = 15):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=minutes)
    return jwt.encode(payload, settings.ACCESS_SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, days: int = 7):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(days=days)
    return jwt.encode(
        payload, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM
    )
