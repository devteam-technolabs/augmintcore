import asyncio
import json
import logging

import websockets

from app.core.redis import redis_client  # your existing redis client

logger = logging.getLogger(__name__)

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

active_workers: dict[str, asyncio.Task] = {}


class CoinbaseWorker:
    def __init__(self, user_id: str, symbol: str):
        self.user_id = user_id
        self.symbol = symbol.upper()
        self.channel = f"user:{user_id}"

    async def start(self):
        backoff = 1
        logger.info(f"CoinbaseWorker started for user={self.user_id}, symbol={self.symbol}")

        while True:
            try:
                async with websockets.connect(
                    COINBASE_WS_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                ) as ws:
                    backoff = 1
                    subscribe_msg = {
                        "type": "subscribe",
                        "channels": [{"name": "ticker", "product_ids": [self.symbol]}],
                    }
                    await ws.send(json.dumps(subscribe_msg))

                    async for raw_msg in ws:
                        data = json.loads(raw_msg)
                        if data.get("type") == "ticker":
                            payload = {
                                "category": "market_price",
                                "symbol": data.get("product_id"),
                                "price": data.get("price"),
                                "open_24h": data.get("open_24h"),
                                "volume_24h": data.get("volume_24h"),
                                "low_24h": data.get("low_24h"),
                                "high_24h": data.get("high_24h"),
                                "best_bid": data.get("best_bid"),
                                "best_ask": data.get("best_ask"),
                                "time": data.get("time"),
                            }
                            await redis_client.publish(self.channel, json.dumps(payload))

            except Exception as e:
                logger.warning(f"CoinbaseWorker error for user={self.user_id}: {e}. Retry in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def update_symbol(self, new_symbol: str):
        """Symbol changes require restarting the worker task."""
        self.symbol = new_symbol.upper()


async def ensure_worker(user_id: str, symbol: str) -> None:
    """Start a CoinbaseWorker task if one isn't running for this user."""
    existing = active_workers.get(user_id)
    if existing and not existing.done():
        return
    worker = CoinbaseWorker(user_id=user_id, symbol=symbol)
    task = asyncio.create_task(worker.start())
    active_workers[user_id] = task


async def restart_worker(user_id: str, symbol: str) -> None:
    """Cancel existing worker and start a new one with updated symbol."""
    existing = active_workers.pop(user_id, None)
    if existing and not existing.done():
        existing.cancel()
        try:
            await existing
        except asyncio.CancelledError:
            pass
    await ensure_worker(user_id, symbol)


# import asyncio
# import json
# import logging
# import traceback
# import websockets

# from app.core.redis import redis_client

# logger = logging.getLogger(__name__)

# COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

# active_workers: dict[str, asyncio.Task] = {}


# class CoinbaseWorker:
#     def __init__(self, user_id: str, symbol: str):
#         self.user_id = user_id
#         self.symbol = symbol.upper()
#         self.channel = f"user:{user_id}"

#     async def start(self):
#         backoff = 1
#         print(f"🚀 CoinbaseWorker START for user={self.user_id}, symbol={self.symbol}")

#         while True:
#             try:
#                 print("🌍 Connecting to Coinbase...")
#                 async with websockets.connect(
#                     COINBASE_WS_URL,
#                     ping_interval=20,
#                     ping_timeout=20,
#                     close_timeout=10,
#                 ) as ws:

#                     print("✅ Connected to Coinbase")

#                     subscribe_msg = {
#                         "type": "subscribe",
#                         "channels": [
#                             {"name": "ticker", "product_ids": [self.symbol]}
#                         ],
#                     }

#                     await ws.send(json.dumps(subscribe_msg))
#                     print("📡 Subscribed to Coinbase ticker")

#                     backoff = 1

#                     async for raw_msg in ws:
#                         print("📥 Message from Coinbase")

#                         data = json.loads(raw_msg)

#                         if data.get("type") == "ticker":
#                             payload = {
#                                 "category": "market_price",
#                                 "symbol": data.get("product_id"),
#                                 "price": data.get("price"),
#                                 "time": data.get("time"),
#                             }

#                             print("📤 Publishing to Redis:", payload)
#                             await redis_client.publish(
#                                 self.channel,
#                                 json.dumps(payload),
#                             )

#             except Exception as e:
#                 print("❌ CoinbaseWorker exception:", e)
#                 traceback.print_exc()
#                 print(f"⏳ Retrying in {backoff}s")
#                 await asyncio.sleep(backoff)
#                 backoff = min(backoff * 2, 60)


# async def ensure_worker(user_id: str, symbol: str) -> None:
#     print("🔍 ensure_worker called for user:", user_id)

#     existing = active_workers.get(user_id)

#     if existing and not existing.done():
#         print("⚠️ Worker already running")
#         return

#     worker = CoinbaseWorker(user_id=user_id, symbol=symbol)
#     task = asyncio.create_task(worker.start())

#     def done_callback(t: asyncio.Task):
#         print("🔥 Worker task finished:", t.exception())

#     task.add_done_callback(done_callback)

#     active_workers[user_id] = task
#     print("✅ Worker created for user:", user_id)


# async def restart_worker(user_id: str, symbol: str) -> None:
#     print("🔄 restart_worker called")

#     existing = active_workers.pop(user_id, None)

#     if existing and not existing.done():
#         print("🛑 Cancelling old worker")
#         existing.cancel()
#         try:
#             await existing
#         except asyncio.CancelledError:
#             print("⚠️ Old worker cancelled")

#     await ensure_worker(user_id, symbol)