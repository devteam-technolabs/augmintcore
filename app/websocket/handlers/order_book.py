import asyncio
import json
import logging

import ccxt.async_support as ccxt
from fastapi import WebSocket

from app.services.coinbase_credentials import get_coinbase_credentials
from app.coinbase.exchange import get_keys

logger = logging.getLogger(__name__)

DEFAULT_SYMBOL = "BTC-USD"
FETCH_INTERVAL = 2  # seconds


async def build_exchange(user_id: int, db):
    print("DEBUG: building exchange for user", user_id)

    keys = await get_keys("coinbase", user_id, db)

    print("DEBUG: keys received", keys)

    exchange = ccxt.coinbaseexchange({
        "apiKey": keys["api_key"],
        "secret": keys["api_secret"],
        "password": keys["passphrase"],
        "enableRateLimit": True,
    })

    print("DEBUG: exchange created")

    return exchange

async def handle_order_book(
    websocket: WebSocket,
    user_id: int,
    db,
    symbol: str = DEFAULT_SYMBOL,
):
    print("DEBUG: handle_order_book started")
    print("DEBUG: user_id:", user_id)
    print("DEBUG: symbol:", symbol)

    symbol = symbol.upper()

    try:
        print("DEBUG: building exchange...")
        exchange = await build_exchange(user_id, db)
        print("DEBUG: exchange built successfully")

    except Exception as e:
        print("❌ ERROR building exchange:", e)
        raise

    try:
        while True:
            try:
                print("DEBUG: fetching orderbook...")
                orderbook = await exchange.fetch_order_book(symbol)
                print("DEBUG: orderbook fetched")

                bids = orderbook["bids"][:10]
                asks = orderbook["asks"][:10]

                payload = {
                    "category": "market_order",
                    "symbol": symbol,
                    "bids": [{"price": b[0], "size": b[1]} for b in bids],
                    "asks": [{"price": a[0], "size": a[1]} for a in asks],
                }

                print("DEBUG: sending payload to websocket")
                await websocket.send_json(payload)
                print("DEBUG: payload sent")

            except Exception as e:
                print("❌ ERROR inside fetch loop:", e)
                raise

            await asyncio.sleep(FETCH_INTERVAL)

    finally:
        print("DEBUG: closing exchange")
        await exchange.close()