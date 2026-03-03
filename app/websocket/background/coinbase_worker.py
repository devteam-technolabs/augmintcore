import asyncio
import json
import logging

import websockets

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

ADVANCED_WS_URL = "wss://advanced-trade-ws.coinbase.com"

# Worker per symbol
symbol_workers: dict[str, asyncio.Task] = {}


class CoinbaseSymbolWorker:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.channel = f"symbol:{self.symbol}"
        self._stop_event = asyncio.Event()

    async def start(self):
        logger.info(f"🚀 SymbolWorker started for {self.symbol}")
        await self._market_listener()

    def stop(self):
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

                    # 🔥 Subscribe to BOTH channels
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

                    logger.info(f"📡 Subscribed to ticker + candles for {self.symbol}")

                    async for raw_msg in ws:
                        if self._stop_event.is_set():
                            break

                        data = json.loads(raw_msg)
                        channel = data.get("channel")

                        # ==========================
                        # TICKER STREAM (FAST)
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
                                    "low_24_h": ticker.get("low_24_h"),
                                    "high_24_h": ticker.get("high_24_h"),
                                    "low_52_w": ticker.get("low_52_w"),
                                    "high_52_w": ticker.get("high_52_w"),
                                    "price_percent_chg_24_h": ticker.get(
                                        "price_percent_chg_24_h"
                                    ),
                                    "best_bid": ticker.get("best_bid"),
                                    "best_ask": ticker.get("best_ask"),
                                    "volume_24h": ticker.get("volume_24h"),
                                    "timestamp": ticker.get("time"),
                                }

                                await redis_client.publish(
                                    self.channel,
                                    json.dumps(payload),
                                )

                        # ==========================
                        # CANDLES STREAM (10s)
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


async def ensure_symbol_worker(symbol: str) -> None:
    symbol = symbol.upper()

    existing = symbol_workers.get(symbol)
    if existing and not existing.done():
        return

    worker = CoinbaseSymbolWorker(symbol)
    task = asyncio.create_task(worker.start())
    symbol_workers[symbol] = task


async def stop_symbol_worker(symbol: str) -> None:
    symbol = symbol.upper()

    task = symbol_workers.pop(symbol, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
