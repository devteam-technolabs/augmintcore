from pydantic import BaseModel, Field
from typing import Optional, Literal


class BuySellOrderRequest(BaseModel):
    exchange_name: str = Field(..., example="coinbase")
    symbol: str = Field(..., example="BTC/USDC")
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: float = Field(..., gt=0, example=0.001)
    total_cost: Optional[float] = Field(None, example=45000),
    limit_price: Optional[float] = Field(None, example=45000)
