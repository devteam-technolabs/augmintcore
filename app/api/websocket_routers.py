from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio
import httpx

from app.websocket.coingecko import fetch_top_ten
from app.websocket.coinbase import coinbase_ws_listener
from app.core.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/market", tags=["Market"])


@router.websocket("/ws/crypto")
async def crypto_socket(websocket: WebSocket):
    await websocket.accept()
    queue = asyncio.Queue()

    try:
        top_ten = await fetch_top_ten()

        await websocket.send_json({
            "type": "TOP_TEN_INIT",
            "data": top_ten
        })

        product_ids = [coin["product_id"] for coin in top_ten]
        asyncio.create_task(coinbase_ws_listener(product_ids, queue))

        while True:
            ticker = await queue.get()
            await websocket.send_json({
                "type": "TICKER_UPDATE",
                "data": {
                    "product_id": ticker["product_id"],
                    "price": ticker["price"],
                    "open_24h": ticker["open_24h"],
                    "time": ticker["time"]
                }
            })

    except WebSocketDisconnect:
        pass


@router.get("/candles/{symbol}")
async def get_price_chart(
    symbol: str,
    granularity: int = Query(3600)
):
    product_id = f"{symbol.upper()}-USD"

    url = (
        settings.COINBASE_REST_URL
        + settings.COINBASE_CANDLES_PATH.format(product_id=product_id)
    )

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url, params={"granularity": granularity})
        res.raise_for_status()

    candles = res.json()

    return {
        "symbol": product_id,
        "granularity": granularity,
        "data": [
            {
                "time": c[0],
                "low": c[1],
                "high": c[2],
                "open": c[3],
                "close": c[4],
                "volume": c[5],
            }
            for c in candles
        ]
    }
