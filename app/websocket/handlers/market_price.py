# import asyncio
# import json
# import logging

# from fastapi import WebSocket

# from app.core.redis import redis_client
# from app.websocket.background.coinbase_worker import ensure_worker, restart_worker

# logger = logging.getLogger(__name__)

# DEFAULT_SYMBOL = "BTC-USD"


# async def handle_market_price(
#     websocket: WebSocket,
#     user_id: str,
#     symbol: str = DEFAULT_SYMBOL,
# ):
#     """
#     Subscribe user to market price feed.
#     Listens to Redis pub/sub channel for this user and
#     forwards messages to the WebSocket.
#     """
#     symbol = symbol.upper()
#     await ensure_worker(user_id, symbol)

#     pubsub = redis_client.pubsub()
#     channel = f"user:{user_id}"
#     await pubsub.subscribe(channel)

#     try:
#         async for message in pubsub.listen():
#             if message["type"] == "message":
#                 data = json.loads(message["data"])
#                 await websocket.send_json(data)
#     finally:
#         await pubsub.unsubscribe(channel)
#         await pubsub.aclose()


# async def change_symbol(user_id: str, new_symbol: str):
#     """Called when frontend sends a symbol change message."""
#     await restart_worker(user_id, new_symbol)

import asyncio
import json
import traceback

from fastapi import WebSocket

from app.core.redis import redis_client
from app.websocket.background.coinbase_worker import ensure_worker

DEFAULT_SYMBOL = "BTC-USD"


async def handle_market_price(
    websocket: WebSocket,
    user_id: str,
    symbol: str = DEFAULT_SYMBOL,
):
    print("📈 handle_market_price START")

    await ensure_worker(user_id, symbol)

    pubsub = redis_client.pubsub()
    channel = f"user:{user_id}"

    print("📡 Subscribing to Redis channel:", channel)
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            print("📬 Redis event:", message)

            if message["type"] == "message":
                data = json.loads(message["data"])
                print("➡️ Sending to client:", data)
                await websocket.send_json(data)

    except Exception as e:
        print("🔥 market_price error:", e)
        traceback.print_exc()

    finally:
        print("🧹 Closing Redis pubsub")
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()