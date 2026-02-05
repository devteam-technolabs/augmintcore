from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserResponse


class ExchangeConnectRequest(BaseModel):
    exchange_name: str  # coinbase
    api_key: str
    api_secret: str
    passphrase: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ExchangeConnectResponse(BaseModel):
    message: str
    user: UserResponse
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    status_code: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class CCTXResponse(BaseModel):
    message: str
    status_code: Optional[int] = None
    data: Optional[list] = None
    model_config = ConfigDict(from_attributes=True)


class UserExchangeResponse(BaseModel):
    id: int
    exchange_name: str
    api_key: Optional[str]
    api_secret: Optional[str]
    passphrase: Optional[str]
    created_at: datetime


class UserExchangeListResponse(BaseModel):
    success: bool
    data: List[UserExchangeResponse]
