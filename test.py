# import asyncio
# import websockets
# import json

# import asyncio
# import websockets
# import json
# from collections import defaultdict

# # Coins we want total volume for
# coins = ["BTC", "ETH", "SOL", "ADA", "XRP", "DOGE", "LTC", "AVAX", "LINK", "MATIC"]

# # Map to keep total USD volume per coin
# total_volume_usd = defaultdict(float)

# async def main():
#     url = "wss://ws-feed.exchange.coinbase.com"

#     async with websockets.connect(url) as ws:
#         # Subscribe to ticker for ALL trading pairs
#         subscribe_message = {
#             "type": "subscribe",
#             "channels": ["ticker"]  # all trading pairs
#         }
#         await ws.send(json.dumps(subscribe_message))
#         print("Subscribed to all tickers!")

#         while True:
#             message = await ws.recv()
#             print(message)  # see raw output

#             data = json.loads(message)

#             if data.get("type") == "ticker":
#                 # Only process if we have price and volume
#                 if "price" in data and "volume_24h" in data:
#                     try:
#                         price = float(data["price"])
#                         volume_base = float(data["volume_24h"])
#                         volume_usd = price * volume_base
#                         data["volume_24h_usd"] = volume_usd
#                     except ValueError:
#                         continue  # skip invalid data

#                     # Determine which coin this pair belongs to
#                     product_id = data["product_id"]  # e.g., BTC-USD, BTC-USDT
#                     base_coin = product_id.split("-")[0]
#                     if base_coin in coins:
#                         total_volume_usd[base_coin] += volume_usd

#             # Print total volume every few messages (or you can use a timer)
#             if len(total_volume_usd) > 0:
#                 print("=== Total 24h USD Volume per Coin ===")
#                 for coin, vol in total_volume_usd.items():
#                     print(f"{coin}: ${vol:,.2f}")
#                 print("==============================\n")

# asyncio.run(main())


# # asyncio.run(main())
# # import asyncio
# # import ccxt.async_support as ccxt
# # from app.coinbase.exchange import clean_private_key
# # API_KEY = "organizations/bf570501-97ef-4c05-8887-1c15c8bef6c0/apiKeys/dee8a277-3638-47e4-844c-0ac81caa33db"
# # API_SECRET = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIPpEkxE4iAtTJtak5sIc1M/p2Zxv9QX29/aBXSp86/SmoAoGCCqGSM49\nAwEHoUQDQgAEFFzN29EsqQMAIII5AUnqA0eEtY6vXSt35REkpWkftvBEaYX0Cb+j\nKpy5nHV2fp4UbuADOY6Grr+lqVsfDT2mbA==\n-----END EC PRIVATE KEY-----\n"


# # async def load_user_portfolio():
# #     exchange = ccxt.coinbaseadvanced({
# #         "apiKey": API_KEY,
# #         "secret": API_SECRET,
# #         "enableRateLimit": True,
# #         "options": {
# #             "brokerage": True,
# #             "fetchMarkets": False,
# #         }
# #     })

# #     try:
# #         # 1️⃣ Fetch balances
# #         balance = await exchange.fetch_balance()

# #         assets = []
# #         total_usd_value = 0.0

# #         # 2️⃣ Load tickers once
# #         tickers = await exchange.fetch_tickers()

# #         for symbol, data in balance.items():
# #             if symbol == "info":
# #                 continue

# #             total = data.get("total", 0)
# #             if not total or total <= 0:
# #                 continue

# #             asset_data = {
# #                 "asset": symbol,
# #                 "free": float(data.get("free", 0)),
# #                 "locked": float(data.get("used", 0)),
# #                 "total": float(total),
# #                 "usd_price": None,
# #                 "usd_value": None,
# #             }

# #             # 3️⃣ USD valuation
# #             if symbol == "USD":
# #                 asset_data["usd_price"] = 1
# #                 asset_data["usd_value"] = asset_data["total"]
# #             else:
# #                 pair = f"{symbol}/USD"
# #                 ticker = tickers.get(pair)

# #                 if ticker and ticker.get("last"):
# #                     price = float(ticker["last"])
# #                     asset_data["usd_price"] = price
# #                     asset_data["usd_value"] = price * asset_data["total"]

# #             if asset_data["usd_value"]:
# #                 total_usd_value += asset_data["usd_value"]

# #             assets.append(asset_data)
# #             print(assets)

# #         return {
# #             "total_assets_value_usd": round(total_usd_value, 2),
# #             "total_currencies": len(assets),
# #             "assets": assets
# #         }

# #     finally:
# #         await exchange.close()


# # asyncio.run(load_user_portfolio())


import asyncio
import json
import threading
from datetime import datetime, timedelta

import ccxt
import numpy as np
import pandas as pd
import websocket
from fastapi import FastAPI, HTTPException, WebSocket

app = FastAPI(title="Crypto Trading Backend")

# ======================
# CCXT COINBASE CONFIG
# ======================
exchange = ccxt.coinbaseexchange(
    {
        "apiKey": "76d97f29a7dba9afae61da53abdc172e",
        "secret": "h3xlRF1bpXKrZM6I03Q4hTn1vw7por2rUM7vL+MK75PW9l3AnY6u/bJZvW30vOCeo81PvN+Mm/RhGjPcpXrJIQ==",
        "password": "5gzc1ji04g2v",
        "enableRateLimit": True,
    }
)

# Sandbox mode (IMPORTANT for testing)
# exchange.set_sandbox_mode(True)

SYMBOL = "ETH/USD"


TIMEFRAME_RULES = {
    "1m": {"tf": "1m", "max_days": 30},
    "15m": {"tf": "15m", "max_days": 90},
    "1h": {"tf": "1h", "max_days": 180},
    "1d": {"tf": "1d", "max_days": 365},
    "1w": {"tf": "1w", "max_days": 1095},
}

PERIOD_MAP = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}


# @app.get("/history")
async def get_historical_data(
    symbol: str = SYMBOL,
    timeframe: str = "1h",  # 1m, 15m, 1h, 1d, 1w
    period: str = "1m",  # 1m, 3m, 6m, 1y
):
    if timeframe not in TIMEFRAME_RULES:
        raise HTTPException(400, "Invalid timeframe")

    if period not in PERIOD_MAP:
        raise HTTPException(400, "Invalid period")

    tf_rule = TIMEFRAME_RULES[timeframe]
    requested_days = PERIOD_MAP[period]

    # Enforce safety limits
    days = min(requested_days, tf_rule["max_days"])

    since = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)

    all_ohlcv = []
    limit = 300
    since_copy = since

    while True:
        ohlcv = exchange.fetch_ohlcv(
            symbol, timeframe=tf_rule["tf"], since=since_copy, limit=limit
        )

        if not ohlcv:
            break

        all_ohlcv.extend(ohlcv)
        print(
            f"Fetched {len(ohlcv)} candles, total so far: {len(all_ohlcv)}", all_ohlcv
        )
        since_copy = ohlcv[-1][0] + 1

        if ohlcv[-1][0] >= exchange.milliseconds():
            break

    df = pd.DataFrame(
        all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "period": period,
        "days_returned": days,
        "candles": df.to_dict(orient="records"),
    }


asyncio.run(get_historical_data())
