import asyncio
import json
import logging

import websockets

logger = logging.getLogger(__name__)

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

TOP_10_PRODUCTS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "MATIC-USD",
]

# Shared in-memory store — updated by listener, read by handler
price_store: dict[str, dict] = {}
_shutdown_event = asyncio.Event()


async def top10_coinbase_listener():
    """
    Persistent listener for top-10 crypto prices from Coinbase WS.
    Runs forever with exponential backoff on failure.
    Stored in price_store dict keyed by product_id.
    """
    logger.info("Top10 Coinbase listener starting...")
    backoff = 1

    while not _shutdown_event.is_set():
        try:
            async with websockets.connect(
                COINBASE_WS_URL,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            ) as ws:
                backoff = 1  # reset on successful connect
                logger.info("Connected to Coinbase WS (top10)")

                subscribe_msg = {
                    "type": "subscribe",
                    "channels": [{"name": "ticker", "product_ids": TOP_10_PRODUCTS}],
                }
                await ws.send(json.dumps(subscribe_msg))

                async for raw_msg in ws:
                    if _shutdown_event.is_set():
                        break
                    data = json.loads(raw_msg)
                    if data.get("type") == "ticker":
                        product_id = data.get("product_id")
                        if product_id:
                            price_store[product_id] = {
                                "symbol": product_id,
                                "price": data.get("price"),
                                "open_24h": data.get("open_24h"),
                                "volume_24h": data.get("volume_24h"),
                                "low_24h": data.get("low_24h"),
                                "high_24h": data.get("high_24h"),
                                "best_bid": data.get("best_bid"),
                                "best_ask": data.get("best_ask"),
                                "side": data.get("side"),
                                "time": data.get("time"),
                            }

        except Exception as e:
            logger.warning(f"Top10 listener error: {e}. Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)  # exponential backoff, max 60s


async def stop_top10_listener():
    _shutdown_event.set()