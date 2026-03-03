import asyncio
import json
import logging
import traceback

from fastapi import WebSocket

from app.core.redis import redis_client
from app.websocket.background.coinbase_worker import ensure_symbol_worker

logger = logging.getLogger(__name__)

DEFAULT_SYMBOL = "BTC-USD"


async def handle_market_price(
    websocket: WebSocket,
    user_id: str,
    symbol: str,
):
    symbol = symbol.upper()

    # 🔥 Ensure symbol worker exists
    await ensure_symbol_worker(symbol)

    pubsub = redis_client.pubsub()
    channel = f"symbol:{symbol}"

    print("📡 Subscribing to:", channel)
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)

    except Exception as e:
        print("🔥 market_price error:", e)

    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
