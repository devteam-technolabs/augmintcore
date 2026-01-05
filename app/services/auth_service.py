from datetime import datetime, timedelta
import re
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

def verify_passwword(passowrd:str):
    if len(passowrd) < 8 or not re.search(r'[A-Z]', passowrd) or not re.search(r'[a-z]', passowrd) or not re.search(r'[0-9]', passowrd) or ' ' in passowrd:
        raise ValueError("Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, one digit, and no spaces.")

    return passowrd