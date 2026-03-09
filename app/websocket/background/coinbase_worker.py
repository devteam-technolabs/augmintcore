import asyncio
import json
import logging
import websockets

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

ADVANCED_WS_URL = "wss://advanced-trade-ws.coinbase.com"

# Worker per symbol
symbol_workers: dict[str, asyncio.Task] = {}

# Track number of active websocket subscribers per symbol
symbol_subscribers: dict[str, int] = {}


class CoinbaseSymbolWorker:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.channel = f"symbol:{self.symbol}"
        self._stop_event = asyncio.Event()

    async def start(self):
        logger.info(f"🚀 SymbolWorker started for {self.symbol}")
        await self._market_listener()

    def stop(self):
        logger.info(f"🛑 Stopping worker for {self.symbol}")
        self._stop_event.set()

    async def _market_listener(self):
        backoff = 1

        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    ADVANCED_WS_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                ) as ws:

                    backoff = 1

                    await ws.send(
                        json.dumps(
                            {
                                "type": "subscribe",
                                "product_ids": [self.symbol],
                                "channel": "ticker",
                            }
                        )
                    )

                    await ws.send(
                        json.dumps(
                            {
                                "type": "subscribe",
                                "product_ids": [self.symbol],
                                "channel": "candles",
                            }
                        )
                    )

                    logger.info(f"📡 Subscribed ticker + candles for {self.symbol}")

                    async for raw_msg in ws:
                        if self._stop_event.is_set():
                            logger.info(f"🛑 Worker loop break for {self.symbol}")
                            break

                        data = json.loads(raw_msg)
                        channel = data.get("channel")

                        # ==========================
                        # TICKER
                        # ==========================
                        if channel == "ticker":
                            for event in data.get("events", []):
                                tickers = event.get("tickers", [])
                                if not tickers:
                                    continue

                                ticker = tickers[0]

                                payload = {
                                    "category": "market_price_ticker",
                                    "symbol": ticker.get("product_id"),
                                    "price": ticker.get("price"),
                                    "best_bid": ticker.get("best_bid"),
                                    "best_ask": ticker.get("best_ask"),
                                    "volume_24h": ticker.get("volume_24h"),
                                    "timestamp": data.get("timestamp"),
                                }

                                await redis_client.publish(
                                    self.channel,
                                    json.dumps(payload),
                                )

                        # ==========================
                        # CANDLES
                        # ==========================
                        elif channel == "candles":
                            for event in data.get("events", []):
                                candles = event.get("candles", [])
                                if not candles:
                                    continue

                                candle = candles[0]

                                payload = {
                                    "category": "market_price_candle",
                                    "symbol": candle.get("product_id"),
                                    "event_type": event.get("type"),
                                    "start": candle.get("start"),
                                    "open": candle.get("open"),
                                    "high": candle.get("high"),
                                    "low": candle.get("low"),
                                    "close": candle.get("close"),
                                    "volume": candle.get("volume"),
                                    "timestamp": data.get("timestamp"),
                                }

                                await redis_client.publish(
                                    self.channel,
                                    json.dumps(payload),
                                )

            except Exception as e:
                logger.warning(
                    f"[Market] symbol={self.symbol} error: {e}. Retry in {backoff}s"
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)


# ===============================
# WORKER MANAGEMENT
# ===============================

async def ensure_symbol_worker(symbol: str) -> None:
    symbol = symbol.upper()

    # Increase subscriber count
    symbol_subscribers[symbol] = symbol_subscribers.get(symbol, 0) + 1
    logger.info(f"👥 Subscribers for {symbol}: {symbol_subscribers[symbol]}")

    existing = symbol_workers.get(symbol)
    if existing and not existing.done():
        return

    worker = CoinbaseSymbolWorker(symbol)
    task = asyncio.create_task(worker.start())
    symbol_workers[symbol] = task


async def remove_symbol_subscriber(symbol: str):
    symbol = symbol.upper()

    if symbol not in symbol_subscribers:
        return

    symbol_subscribers[symbol] -= 1

    logger.info(f"👥 Subscribers for {symbol}: {symbol_subscribers[symbol]}")

    if symbol_subscribers[symbol] <= 0:
        logger.info(f"⚠️ No subscribers left for {symbol}, stopping worker")
        symbol_subscribers.pop(symbol, None)
        await stop_symbol_worker(symbol)


async def stop_symbol_worker(symbol: str) -> None:
    symbol = symbol.upper()

    task = symbol_workers.pop(symbol, None)

    if task and not task.done():
        logger.info(f"🛑 Cancelling worker for {symbol}")
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"✅ Worker stopped for {symbol}")

# import asyncio
# import json
# import logging

# import websockets

# from app.core.redis import redis_client

# logger = logging.getLogger(__name__)

# ADVANCED_WS_URL = "wss://advanced-trade-ws.coinbase.com"

# # Worker per symbol
# symbol_workers: dict[str, asyncio.Task] = {}


# class CoinbaseSymbolWorker:
#     def __init__(self, symbol: str):
#         self.symbol = symbol.upper()
#         self.channel = f"symbol:{self.symbol}"
#         self._stop_event = asyncio.Event()

#     async def start(self):
#         logger.info(f"🚀 SymbolWorker started for {self.symbol}")
#         await self._market_listener()

#     def stop(self):
#         self._stop_event.set()

#     async def _market_listener(self):
#         backoff = 1

#         while not self._stop_event.is_set():
#             try:
#                 async with websockets.connect(
#                     ADVANCED_WS_URL,
#                     ping_interval=20,
#                     ping_timeout=20,
#                     close_timeout=10,
#                 ) as ws:

#                     backoff = 1

#                     # 🔥 Subscribe to BOTH channels
#                     await ws.send(
#                         json.dumps(
#                             {
#                                 "type": "subscribe",
#                                 "product_ids": [self.symbol],
#                                 "channel": "ticker",
#                             }
#                         )
#                     )

#                     await ws.send(
#                         json.dumps(
#                             {
#                                 "type": "subscribe",
#                                 "product_ids": [self.symbol],
#                                 "channel": "candles",
#                             }
#                         )
#                     )

#                     logger.info(f"📡 Subscribed to ticker + candles for {self.symbol}")

#                     async for raw_msg in ws:
#                         if self._stop_event.is_set():
#                             break

#                         data = json.loads(raw_msg)
#                         channel = data.get("channel")

#                         # ==========================
#                         # TICKER STREAM (FAST)
#                         # ==========================
#                         if channel == "ticker":
#                             for event in data.get("events", []):
#                                 tickers = event.get("tickers", [])
#                                 if not tickers:
#                                     continue

#                                 ticker = tickers[0]
#                                 timestamp = data.get("timestamp")

#                                 payload = {
#                                     "category": "market_price_ticker",
#                                     "symbol": ticker.get("product_id"),
#                                     "price": ticker.get("price"),
#                                     "low_24_h": ticker.get("low_24_h"),
#                                     "high_24_h": ticker.get("high_24_h"),
#                                     "low_52_w": ticker.get("low_52_w"),
#                                     "high_52_w": ticker.get("high_52_w"),
#                                     "price_percent_chg_24_h": ticker.get(
#                                         "price_percent_chg_24_h"
#                                     ),
#                                     "best_bid": ticker.get("best_bid"),
#                                     "best_ask": ticker.get("best_ask"),
#                                     "volume_24h": ticker.get("volume_24h"),
#                                     "best_bid_quantity": ticker.get("best_bid_quantity"),
#                                     "best_ask_quantity": ticker.get("best_ask_quantity"),
#                                     "timestamp": timestamp,
#                                 }

#                                 await redis_client.publish(
#                                     self.channel,
#                                     json.dumps(payload),
#                                 )

#                         # ==========================
#                         # CANDLES STREAM (10s)
#                         # ==========================
#                         elif channel == "candles":
#                             for event in data.get("events", []):
#                                 candles = event.get("candles", [])
#                                 if not candles:
#                                     continue

#                                 candle = candles[0]

#                                 payload = {
#                                     "category": "market_price_candle",
#                                     "symbol": candle.get("product_id"),
#                                     "event_type": event.get("type"),
#                                     "start": candle.get("start"),
#                                     "open": candle.get("open"),
#                                     "high": candle.get("high"),
#                                     "low": candle.get("low"),
#                                     "close": candle.get("close"),
#                                     "volume": candle.get("volume"),
#                                     "timestamp": data.get("timestamp"),
#                                 }

#                                 await redis_client.publish(
#                                     self.channel,
#                                     json.dumps(payload),
#                                 )

#             except Exception as e:
#                 logger.warning(
#                     f"[Market] symbol={self.symbol} error: {e}. Retry in {backoff}s"
#                 )
#                 await asyncio.sleep(backoff)
#                 backoff = min(backoff * 2, 60)


# async def ensure_symbol_worker(symbol: str) -> None:
#     symbol = symbol.upper()

#     existing = symbol_workers.get(symbol)
#     if existing and not existing.done():
#         return

#     worker = CoinbaseSymbolWorker(symbol)
#     task = asyncio.create_task(worker.start())
#     symbol_workers[symbol] = task

# async def remove_symbol_subscriber(symbol: str):
#     symbol = symbol.upper()

#     if symbol_subscribers[symbol] > 0:
#         symbol_subscribers[symbol] -= 1

#     if symbol_subscribers[symbol] == 0:
#         await stop_symbol_worker(symbol)


# async def stop_symbol_worker(symbol: str) -> None:
#     symbol = symbol.upper()

#     task = symbol_workers.pop(symbol, None)
#     if task and not task.done():
#         task.cancel()
#         try:
#             await task
#         except asyncio.CancelledError:
#             pass

# import asyncio
# import json
# import logging
# import websockets
# from datetime import datetime
# from collections import defaultdict

# from app.core.redis import redis_client

# logger = logging.getLogger(__name__)

# ADVANCED_WS_URL = "wss://advanced-trade-ws.coinbase.com"

# symbol_workers: dict[str, asyncio.Task] = {}
# symbol_candles: dict[str, dict] = {}
# symbol_subscribers: dict[str, int] = defaultdict(int)


# async def safe_publish(channel: str, message: str):
#     """Safely publish with retry."""
#     for attempt in range(3):
#         try:
#             await redis_client.publish(channel, message)
#             logger.debug(f"✅ Published to {channel}")
#             return
#         except Exception as e:
#             logger.warning(f"Publish failed (attempt {attempt+1}): {e}")
#             if attempt < 2:
#                 await asyncio.sleep(0.1)
#     logger.error(f"❌ Publish failed after 3 retries: {channel}")


# async def update_local_candle(symbol: str, price: float, timestamp: str, size: float = 0.0):
#     dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
#     minute_bucket = dt.replace(second=0, microsecond=0)

#     current = symbol_candles.get(symbol)

#     # New minute
#     if not current or current["minute"] != minute_bucket:
#         # Emit final candle before switching
#         if current:
#             await safe_publish(
#                 f"symbol:{symbol}",
#                 json.dumps({
#                     "category": "market_price_candle",
#                     "symbol": symbol,
#                     "start": current["minute"].isoformat(),
#                     "open": current["open"],
#                     "high": current["high"],
#                     "low": current["low"],
#                     "close": current["close"],
#                     "volume": current["volume"],
#                     "final": True,
#                 })
#             )
#             logger.info(f"🔥 Final candle sent for {symbol}: {current['minute']}")

#         # Create new candle
#         symbol_candles[symbol] = {
#             "minute": minute_bucket,
#             "open": price,
#             "high": price,
#             "low": price,
#             "close": price,
#             "volume": size,
#         }

#     else:
#         current["high"] = max(current["high"], price)
#         current["low"] = min(current["low"], price)
#         current["close"] = price
#         current["volume"] += size  # Accumulate volume

#     # 🔥 ALWAYS publish updating candle
#     candle = symbol_candles[symbol]
#     await safe_publish(
#         f"symbol:{symbol}",
#         json.dumps({
#             "category": "market_price_candle",
#             "symbol": symbol,
#             "start": candle["minute"].isoformat(),
#             "open": candle["open"],
#             "high": candle["high"],
#             "low": candle["low"],
#             "close": candle["close"],
#             "volume": candle["volume"],
#             "final": False,
#         })
#     )
#     logger.debug(f"📊 Live candle update: {symbol} {candle['minute'].isoformat()[:16]} O:{candle['open']:.4f} H:{candle['high']:.4f} L:{candle['low']:.4f} C:{candle['close']:.4f} V:{candle['volume']:.2f}")


# # ==========================================================
# # Worker Per Symbol
# # ==========================================================

# class CoinbaseSymbolWorker:
#     def __init__(self, symbol: str):
#         self.symbol = symbol.upper()
#         self.channel = f"symbol:{self.symbol}"
#         self._stop_event = asyncio.Event()

#     async def start(self):
#         logger.info(f"🚀 Worker started for {self.symbol}")
#         await self._ticker_listener()

#     async def _ticker_listener(self):
#         backoff = 1

#         while not self._stop_event.is_set():
#             try:
#                 async with websockets.connect(
#                     ADVANCED_WS_URL,
#                     ping_interval=20,
#                     ping_timeout=20,
#                     close_timeout=10,
#                 ) as ws:

#                     await ws.send(json.dumps({
#                         "type": "subscribe",
#                         "product_ids": [self.symbol],
#                         "channel": "ticker",
#                     }))

#                     logger.info(f"📡 Subscribed to ticker for {self.symbol}")
#                     backoff = 1

#                     async for raw_msg in ws:
#                         if self._stop_event.is_set():
#                             break

#                         data = json.loads(raw_msg)

#                         if data.get("channel") != "ticker":
#                             continue

#                         for event in data.get("events", []):
#                             tickers = event.get("tickers", [])
#                             if not tickers:
#                                 continue

#                             ticker = tickers[0]

#                             price = float(ticker.get("price", 0))
#                             size = float(ticker.get("size", 0))  # Volume from ticker
#                             timestamp = ticker.get("time")

#                             # 🔥 Publish ticker instantly
#                             ticker_payload = {
#                                 "category": "market_price_ticker",
#                                 "symbol": ticker.get("product_id"),
#                                 "price": price,
#                                 "low_24_h": ticker.get("low_24_h"),
#                                 "high_24_h": ticker.get("high_24_h"),
#                                 "low_52_w": ticker.get("low_52_w"),
#                                 "high_52_w": ticker.get("high_52_w"),
#                                 "price_percent_chg_24_h": ticker.get("price_percent_chg_24_h"),
#                                 "best_bid": ticker.get("best_bid"),
#                                 "best_ask": ticker.get("best_ask"),
#                                 "volume_24h": ticker.get("volume_24h"),
#                                 "timestamp": timestamp,
#                             }

#                             await safe_publish(self.channel, json.dumps(ticker_payload))
#                             logger.debug(f"💰 Ticker published: {self.symbol} ${price}")

#                             # Build candle locally
#                             await update_local_candle(self.symbol, price, timestamp, size)

#             except Exception as e:
#                 logger.warning(f"[Worker] {self.symbol} error: {e}. Retry in {backoff}s")
#                 await asyncio.sleep(backoff)
#                 backoff = min(backoff * 2, 60)


# async def ensure_symbol_worker(symbol: str):
#     symbol = symbol.upper()

#     existing = symbol_workers.get(symbol)
#     if existing and not existing.done():
#         return

#     worker = CoinbaseSymbolWorker(symbol)
#     task = asyncio.create_task(worker.start())
#     symbol_workers[symbol] = task


# async def remove_symbol_subscriber(symbol: str):
#     symbol = symbol.upper()

#     if symbol_subscribers[symbol] > 0:
#         symbol_subscribers[symbol] -= 1

#     if symbol_subscribers[symbol] == 0:
#         await stop_symbol_worker(symbol)


# async def stop_symbol_worker(symbol: str):
#     symbol = symbol.upper()

#     task = symbol_workers.pop(symbol, None)
#     if task and not task.done():
#         logger.info(f"🛑 Stopping worker for {symbol}")
#         task.cancel()
#         try:
#             await task
#         except asyncio.CancelledError:
#             pass

#     symbol_subscribers.pop(symbol, None)
#     symbol_candles.pop(symbol, None)
#     logger.info(f"🧹 Cleaned up {symbol}")
