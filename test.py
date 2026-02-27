import asyncio
# # import websockets
# # import json

# # import asyncio
# # import websockets
# # import json
# # from collections import defaultdict

# # # Coins we want total volume for
# # coins = ["BTC", "ETH", "SOL", "ADA", "XRP", "DOGE", "LTC", "AVAX", "LINK", "MATIC"]

# # # Map to keep total USD volume per coin
# # total_volume_usd = defaultdict(float)

# # async def main():
# #     url = "wss://ws-feed.exchange.coinbase.com"

# #     async with websockets.connect(url) as ws:
# #         # Subscribe to ticker for ALL trading pairs
# #         subscribe_message = {
# #             "type": "subscribe",
# #             "channels": ["ticker"]  # all trading pairs
# #         }
# #         await ws.send(json.dumps(subscribe_message))
# #         print("Subscribed to all tickers!")

# #         while True:
# #             message = await ws.recv()
# #             print(message)  # see raw output

# #             data = json.loads(message)

# #             if data.get("type") == "ticker":
# #                 # Only process if we have price and volume
# #                 if "price" in data and "volume_24h" in data:
# #                     try:
# #                         price = float(data["price"])
# #                         volume_base = float(data["volume_24h"])
# #                         volume_usd = price * volume_base
# #                         data["volume_24h_usd"] = volume_usd
# #                     except ValueError:
# #                         continue  # skip invalid data

# #                     # Determine which coin this pair belongs to
# #                     product_id = data["product_id"]  # e.g., BTC-USD, BTC-USDT
# #                     base_coin = product_id.split("-")[0]
# #                     if base_coin in coins:
# #                         total_volume_usd[base_coin] += volume_usd

# #             # Print total volume every few messages (or you can use a timer)
# #             if len(total_volume_usd) > 0:
# #                 print("=== Total 24h USD Volume per Coin ===")
# #                 for coin, vol in total_volume_usd.items():
# #                     print(f"{coin}: ${vol:,.2f}")
# #                 print("==============================\n")

# # asyncio.run(main())


# # # asyncio.run(main())
# # # import asyncio
# # # import ccxt.async_support as ccxt
# # # from app.coinbase.exchange import clean_private_key
# # # API_KEY = "organizations/bf570501-97ef-4c05-8887-1c15c8bef6c0/apiKeys/dee8a277-3638-47e4-844c-0ac81caa33db"
# # # API_SECRET = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIPpEkxE4iAtTJtak5sIc1M/p2Zxv9QX29/aBXSp86/SmoAoGCCqGSM49\nAwEHoUQDQgAEFFzN29EsqQMAIII5AUnqA0eEtY6vXSt35REkpWkftvBEaYX0Cb+j\nKpy5nHV2fp4UbuADOY6Grr+lqVsfDT2mbA==\n-----END EC PRIVATE KEY-----\n"


# # # async def load_user_portfolio():
# # #     exchange = ccxt.coinbaseadvanced({
# # #         "apiKey": API_KEY,
# # #         "secret": API_SECRET,
# # #         "enableRateLimit": True,
# # #         "options": {
# # #             "brokerage": True,
# # #             "fetchMarkets": False,
# # #         }
# # #     })

# # #     try:
# # #         # 1️⃣ Fetch balances
# # #         balance = await exchange.fetch_balance()

# # #         assets = []
# # #         total_usd_value = 0.0

# # #         # 2️⃣ Load tickers once
# # #         tickers = await exchange.fetch_tickers()

# # #         for symbol, data in balance.items():
# # #             if symbol == "info":
# # #                 continue

# # #             total = data.get("total", 0)
# # #             if not total or total <= 0:
# # #                 continue

# # #             asset_data = {
# # #                 "asset": symbol,
# # #                 "free": float(data.get("free", 0)),
# # #                 "locked": float(data.get("used", 0)),
# # #                 "total": float(total),
# # #                 "usd_price": None,
# # #                 "usd_value": None,
# # #             }

# # #             # 3️⃣ USD valuation
# # #             if symbol == "USD":
# # #                 asset_data["usd_price"] = 1
# # #                 asset_data["usd_value"] = asset_data["total"]
# # #             else:
# # #                 pair = f"{symbol}/USD"
# # #                 ticker = tickers.get(pair)

# # #                 if ticker and ticker.get("last"):
# # #                     price = float(ticker["last"])
# # #                     asset_data["usd_price"] = price
# # #                     asset_data["usd_value"] = price * asset_data["total"]

# # #             if asset_data["usd_value"]:
# # #                 total_usd_value += asset_data["usd_value"]

# # #             assets.append(asset_data)
# # #             print(assets)

# # #         return {
# # #             "total_assets_value_usd": round(total_usd_value, 2),
# # #             "total_currencies": len(assets),
# # #             "assets": assets
# # #         }

# # #     finally:
# # #         await exchange.close()


# # # asyncio.run(load_user_portfolio())


# from fastapi import FastAPI, WebSocket
# import ccxt
# import pandas as pd
# import numpy as np
# import json
# import asyncio
# import websocket
# import threading
# from datetime import datetime, timedelta
# from fastapi import HTTPException

# app = FastAPI(title="Crypto Trading Backend")

# # ======================
# # CCXT COINBASE CONFIG
# # ======================
# exchange = ccxt.coinbaseexchange({
#     "apiKey": "76d97f29a7dba9afae61da53abdc172e",
#     "secret": "h3xlRF1bpXKrZM6I03Q4hTn1vw7por2rUM7vL+MK75PW9l3AnY6u/bJZvW30vOCeo81PvN+Mm/RhGjPcpXrJIQ==",
#     "password": "5gzc1ji04g2v",
#     "enableRateLimit": True,
# })

# # Sandbox mode (IMPORTANT for testing)
# # exchange.set_sandbox_mode(True)

# SYMBOL = "XRP/USD"


# TIMEFRAME_RULES = {
#     "1m":  {"tf": "1m",  "max_days": 30},
#     "15m": {"tf": "15m", "max_days": 90},
#     "1h":  {"tf": "1h",  "max_days": 180},
#     "1d":  {"tf": "1d",  "max_days": 365},
#     "1w":  {"tf": "1w",  "max_days": 1095},
# }

# PERIOD_MAP = {
#     "1m": 30,
#     "3m": 90,
#     "6m": 180,
#     "1y": 365,
# }

# # @app.get("/history")
# async def get_historical_data(
#     symbol: str = SYMBOL,
#     timeframe: str = "1h",   # 1m, 15m, 1h, 1d, 1w
#     period: str = "1m"       # 1m, 3m, 6m, 1y
# ):
#     if timeframe not in TIMEFRAME_RULES:
#         raise HTTPException(400, "Invalid timeframe")

#     if period not in PERIOD_MAP:
#         raise HTTPException(400, "Invalid period")

#     tf_rule = TIMEFRAME_RULES[timeframe]
#     requested_days = PERIOD_MAP[period]

#     # Enforce safety limits
#     days = min(requested_days, tf_rule["max_days"])

#     since = int(
#         (datetime.utcnow() - timedelta(days=days)).timestamp() * 1000
#     )

#     all_ohlcv = []
#     limit = 300
#     since_copy = since

#     while True:
#         ohlcv = exchange.fetch_ohlcv(
#             symbol,
#             timeframe=tf_rule["tf"],
#             since=since_copy,
#             limit=limit
#         )

#         if not ohlcv:
#             break

#         all_ohlcv.extend(ohlcv)
#         print(f"Fetched {len(ohlcv)} candles, total so far: {len(all_ohlcv)}", all_ohlcv)
#         since_copy = ohlcv[-1][0] + 1

#         if ohlcv[-1][0] >= exchange.milliseconds():
#             break

#     df = pd.DataFrame(
#         all_ohlcv,
#         columns=["timestamp", "open", "high", "low", "close", "volume"]
#     )

#     df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

#     return {
#         "symbol": symbol,
#         "timeframe": timeframe,
#         "period": period,
#         "days_returned": days,
#         "candles": df.to_dict(orient="records"),
#     }

# asyncio.run(get_historical_data())


# import asyncio
# import json

# import uvicorn
# import websockets
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# COINBASE_WS = "wss://ws-feed.exchange.coinbase.com"

# # FIXED ORDERBOOK STORAGE
# orderbook = {"bids": {}, "asks": {}, "last_trade": None}

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# def update_book(side, price, size):
#     p = float(price)
#     s = float(size)

#     book = orderbook["bids"] if side == "buy" else orderbook["asks"]

#     # REMOVE LEVEL
#     if s == 0:
#         if p in book:
#             del book[p]
#     else:
#         book[p] = s


# async def coinbase_orderbook_ws(product_id="BTC-USD"):
#     subscribe_msg = {
#         "type": "subscribe",
#         "channels": [
#             {"name": "level2", "product_ids": [product_id]},
#             {"name": "matches", "product_ids": [product_id]},
#         ],
#     }

#     while True:
#         try:
#             async with websockets.connect(COINBASE_WS) as ws:

#                 await ws.send(json.dumps(subscribe_msg))
#                 print("Connected to Coinbase WS")

#                 async for raw in ws:
#                     data = json.loads(raw)

#                     # SNAPSHOT (full book)
#                     if data.get("type") == "snapshot":
#                         orderbook["bids"] = {
#                             float(p): float(s) for p, s in data["bids"]
#                         }
#                         orderbook["asks"] = {
#                             float(p): float(s) for p, s in data["asks"]
#                         }

#                     # ORDER UPDATES
#                     elif data.get("type") == "l2update":
#                         for side, price, size in data["changes"]:
#                             update_book(side, price, size)

#                     # LAST TRADE
#                     elif data.get("type") == "match":
#                         orderbook["last_trade"] = {
#                             "price": data["price"],
#                             "size": data["size"],
#                             "side": data["side"],
#                             "time": data["time"],
#                         }

#         except Exception as e:
#             print("WebSocket Error → Reconnecting:", e)
#             await asyncio.sleep(3)


# @app.get("/orderbook")
# async def get_orderbook():
#     bids = sorted(orderbook["bids"].items(), key=lambda x: -x[0])[:20]
#     asks = sorted(orderbook["asks"].items(), key=lambda x: x[0])[:20]

#     return {
#         "bids": [{"price": p, "size": s} for p, s in bids],
#         "asks": [{"price": p, "size": s} for p, s in asks],
#         "last_trade": orderbook["last_trade"],
#     }


# @app.on_event("startup")
# async def start_socket():
#     asyncio.create_task(coinbase_orderbook_ws())


# if __name__ == "__main__":
#     uvicorn.run("test:app", host="0.0.0.0", port=8000, reload=True)


# Adding a comment for testing
# import ccxt.async_support as ccxt
# from app.coinbase.coinbase_cctx import get_working_coinbase_exchange




# keys = {
#         "api_key": "organizations/dce12743-0903-4c2b-88d4-49ad95cce694/apiKeys/e891dae7-04ce-4f09-b430-7e21faa70a72",
#         "api_secret": '-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIJ9kz/KWvnsto9q1xOGkLP08c4mmtIipH0YhM7QBeNT9oAoGCCqGSM49\nAwEHoUQDQgAEpodAXPGHGejhvpc5CQ7Is4gIzJuTcUas+UGTk99l4oOnpTNZCyyD\n7BYgYPBqmwc0LDaGvcth2QUIz/Z6QiglDg==\n-----END EC PRIVATE KEY-----\n',
#         "passphrase": None,
#     }
            
# api_key = keys["api_key"]
# api_secret = keys["api_secret"]
# passphrase = keys.get("passphrase")

# async def calculate_total_trade_value():
#     exchange =None

#     try:
#         exchange = await get_working_coinbase_exchange(
#             keys["api_key"],
#             keys["api_secret"],
#             keys.get("passphrase", "")
#         )
#         trades = await exchange.fetch_my_trades()
#         total_trade_value = 0.0
#         trade_count = 0
#         for trade in trades:
#             if trade['side'] == "buy":
#                 cost = trade["cost"]
#                 if cost :
#                     total_trade_value += cost
#                     trade_count +=1
#         return round(total_trade_value, 2), trade_count

#     finally:
#         if exchange:
#             await exchange.close()
# async def calculate_portfolio_metrics(base_currency="USD"):
#     exchange = None

#     try:
#         exchange = await get_working_coinbase_exchange(
#             keys["api_key"],
#             keys["api_secret"],
#             keys.get("passphrase", "")
#         )

#         balance = (
#             exchange._cached_validation_balance
#             if hasattr(exchange, "_cached_validation_balance")
#             else await exchange.fetch_balance()
#         )
#         total_assets_balance = balance["total"]
#         STABLE_COINS = {"USDC", "USDT"}

#         portfolio_value = 0.0
#         total_cost_basis = 0.0
#         asset_breakdown = {}

#         for asset, amount in total_assets_balance.items():
#             if amount == 0:
#                 continue

#             if asset in STABLE_COINS:
#                 usd_value = amount
#             else:
#                 symbol = f"{asset}/USD"
#                 ticker = await exchange.fetch_ticker(symbol)
#                 price = ticker["last"]
#                 usd_value = amount * price

#             portfolio_value += usd_value
#             asset_breakdown[asset] = round(usd_value, 2)

#         ###For the total cost basis
#         trades = await exchange.fetch_my_trades()
#         for trade in trades:
#             if trade['side']=="buy":
#                 cost = trade['cost']
#                 if cost :
#                     total_cost_basis+=cost
#         unrealised_pl = portfolio_value - total_cost_basis


#     finally:
#         if exchange:
#             await exchange.close()



    #     print(balance)
    #     holdings = {curr: amt for curr, amt in balance['total'].items() if amt > 0}
        
    #     total_portfolio_value = 0.0
    #     portfolio_value_24h_ago = 0.0

    #     # 1. Calculate Total Value and 24h P/L
    #     for currency, amount in holdings.items():
    #         if currency == base_currency:
    #             # If holding USD, just add the raw amount
    #             total_portfolio_value += amount
    #             portfolio_value_24h_ago += amount
    #             continue # Skip the ticker fetch for USD
                
    #         symbol = f"{currency}/{base_currency}"
                    
    #         try:
    #             # Fetch 24h ticker data
    #             ticker = await exchange.fetch_ticker(symbol)
                
    #             # Safely get prices, defaulting to 0 if missing
    #             current_price = ticker.get('last', 0)
    #             open_price = ticker.get('open', 0)
                
    #             # Multiply amount by price!
    #             total_portfolio_value += (amount * current_price)
                
    #             if open_price:
    #                 portfolio_value_24h_ago += (amount * open_price)
    #             else:
    #                 # Fallback if 'open' isn't provided
    #                 portfolio_value_24h_ago += (amount * current_price)
                    
    #         except ccxt.BadSymbol:
    #             print(f"Skipping {symbol} - not found on Coinbase.")
    #         except Exception as e:
    #             print(f"Error fetching ticker for {symbol}: {e}")
                
    #     # Calculate 24h differences outside the loop
    #     pl_24h = total_portfolio_value - portfolio_value_24h_ago
    #     pl_24h_percentage = (pl_24h / portfolio_value_24h_ago) * 100 if portfolio_value_24h_ago > 0 else 0

    #     # 2. Calculate Cost Basis
    #     total_cost_basis = 0.0
    #     for currency in holdings.keys():
    #         if currency == base_currency: 
    #             continue
                
    #         symbol = f"{currency}/{base_currency}"
    #         try:
    #             # Fetch historical trades for this specific pair
    #             trades = await exchange.fetch_my_trades(symbol)
                    
    #             for trade in trades:
    #                 if trade['side'] == 'buy':
    #                     total_cost_basis += trade['cost'] 
    #                 elif trade['side'] == 'sell':
    #                     total_cost_basis -= trade['cost']
                            
    #         except Exception as e:
    #             print(f"Could not fetch trades for {symbol}: {e}")

    #     # 3. Calculate Total P/L (Outside the loop!)
    #     total_pl = total_portfolio_value - total_cost_basis
    #     total_pl_percentage = (total_pl / total_cost_basis) * 100 if total_cost_basis > 0 else 0

    #     return {
    #         "Total Portfolio Value": round(total_portfolio_value, 2),
    #         "P/L 24h ($)": round(pl_24h, 2),
    #         "P/L 24h (%)": round(pl_24h_percentage, 2),
    #         "Cost Basis": round(total_cost_basis, 2),
    #         "Total P/L ($)": round(total_pl, 2),
    #         "Total P/L (%)": round(total_pl_percentage, 2)
    #     }

    # except ccxt.NetworkError as e:
    #     print(f"Network error: {e}")
    # except ccxt.ExchangeError as e:
    #     print(f"Exchange error: {e}")
    # finally:
    #     # THIS FIXES THE WARNING: Always close the connection
    #     if exchange is not None:
    #         await exchange.close()

# Run the calculation
# metrics = asyncio.run(calculate_total_trade_value())
# print(metrics)

import asyncio
import json
import websockets

COINBASE_WS_URL = "wss://advanced-trade-ws.coinbase.com"


async def main():
    print("🌍 Connecting to Coinbase Advanced Trade WebSocket...")

    async with websockets.connect(
        COINBASE_WS_URL,
        ping_interval=20,
        ping_timeout=20,
    ) as ws:

        print("✅ Connected!")

        subscribe_message = {
            "type": "subscribe",
            "product_ids": ["ETH-USD"],
            "channel": "candles"
        }

        print("📡 Sending subscribe message...")
        await ws.send(json.dumps(subscribe_message))
        print("📡 Subscribed to ETH-USD candles")

        print("⏳ Listening for messages...\n")

        async for message in ws:
            print("📥 RAW MESSAGE:")
            print(message)
            print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())