from pydantic import BaseModel, Field
from typing import Optional, Literal


class BuySellOrderRequest(BaseModel):
    exchange_name: str = Field(..., example="coinbase")
    symbol: str = Field(..., example="BTC/USD")
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: float = Field(..., gt=0, example=0.001)
    price: Optional[float] = Field(None, gt=0, example=45000)
