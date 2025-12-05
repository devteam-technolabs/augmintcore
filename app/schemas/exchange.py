from pydantic import BaseModel, ConfigDict
from typing import Optional
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