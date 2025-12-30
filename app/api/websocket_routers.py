from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import time

from app.websocket.coingecko import fetch_top_ten
from app.websocket.coinbase import coinbase_ws_listener
from app.core.config import get_settings
from app.websocket.candels import fetch_candles
from datetime import datetime, timezone


settings = get_settings()

router = APIRouter(prefix="/market", tags=["Market"])


@router.websocket("/ws/crypto")
@router.websocket("/ws/crypto/")
async def crypto_socket(websocket: WebSocket):
    await websocket.accept()

    ticker_queue = asyncio.Queue()

    symbol = websocket.query_params.get("symbol")
    granularity = int(websocket.query_params.get("granularity", 900))

    try:
        if symbol:
            symbol = symbol.upper()
            product_id = f"{symbol}-USD"

            last_candle_time = None  # ✅ track last candle

            async def candle_loop():
                nonlocal last_candle_time

                while True:
                    candle = await fetch_candles(symbol, granularity)

                    if candle:
                        candle_time = candle["time"]

                        # ✅ SEND ONLY IF NEW CANDLE
                        if candle_time != last_candle_time:
                            last_candle_time = candle_time

                            utc_time = datetime.fromtimestamp(
                                candle_time, tz=timezone.utc
                            )

                            await websocket.send_json({
                                "type": "Price_Chart",
                                "symbol": product_id,
                                "price": candle["close"],
                                "granularity": granularity,
                                "volume": candle["volume"],
                                # "time": candle_time,                 # unix UTC
                                "time_iso": utc_time.isoformat(),    # decoded
                            })

                    await asyncio.sleep(1)

            async def ticker_loop():
                while True:
                    ticker = await ticker_queue.get()

                    volume = (
                        float(ticker.get("volume"))
                        if ticker.get("volume") is not None
                        else float(ticker.get("last_size", 0))
                    )

                    await websocket.send_json({
                        "type": "Price_Chart",
                        "symbol": product_id,
                        "price": float(ticker["price"]),
                        "granularity": granularity,
                        "time": int(time.time()),   # realtime tick (UTC)
                        "volume": volume,
                    })

            asyncio.create_task(
                coinbase_ws_listener([product_id], ticker_queue)
            )

            await asyncio.gather(
                candle_loop(),
                ticker_loop(),
            )

        # =====================================================
        # 🔹 TOP TEN MODE (EVERY TICK UPDATE)
        # =====================================================
        else:
            price_cache = {}
            last_top_ten = []
            sparkline_len = 100

            top_ten = await fetch_top_ten()
            product_ids = [coin["product_id"] for coin in top_ten]

            # 🔹 initialize cache ONCE
            for coin in top_ten:
                pid = coin["product_id"]
                price_cache[pid] = {
                    "price": float(coin["price"]),
                    "change": float(coin.get("change", 0)),
                    "sparkline": [float(coin["price"])]
                }

            formatted_top_ten = [
                {
                    "id": coin.get("id", coin["product_id"].lower()),
                    "symbol": coin["product_id"],
                    "name": f"{coin['product_id']}/USD",
                    "icon": coin.get("icon", ""),
                    "price": price_cache[coin["product_id"]]["price"],
                    "change": price_cache[coin["product_id"]]["change"],
                    "sparkline": price_cache[coin["product_id"]]["sparkline"]
                }
                for coin in top_ten
            ]

            await websocket.send_json({
                "type": "Top Ten Coins",
                "channel": "TOP_TEN_COINS",
                "data": formatted_top_ten,
            })

            asyncio.create_task(
                coinbase_ws_listener(product_ids, ticker_queue)
            )

            # =====================================================
            # 🔹 LIVE UPDATES
            # =====================================================
            while True:
                ticker = await ticker_queue.get()

                product_id = ticker["product_id"]
                price = float(ticker["price"])

                if product_id not in price_cache:
                    continue  # ignore non top-10 coins

                open_24h = float(ticker.get("open_24h", price))
                change = (price - open_24h) / open_24h if open_24h else 0

                # update cache
                price_cache[product_id]["price"] = price
                price_cache[product_id]["open_24h"] = open_24h
                price_cache[product_id]["change"] = change
                price_cache[product_id]["sparkline"].append(price)

                if len(price_cache[product_id]["sparkline"]) > sparkline_len:
                    price_cache[product_id]["sparkline"].pop(0)

                # 🔹 SEND SINGLE COIN UPDATE (THIS IS WHAT YOU WANT)
                await websocket.send_json({
                    "type": "Top Ten Coins",
                    "symbol": product_id,
                    "product_id": product_id,
                    "price": f"{price:.2f}",
                    "open_24h": f"{open_24h:.2f}",
                    "change": f"{change:.6f}",
                    "time": datetime.now(timezone.utc).isoformat()
                })

    except WebSocketDisconnect:
        print("❌ WebSocket disconnected")












# 5:34
# @router.websocket("/ws/crypto")
# async def crypto_socket(websocket: WebSocket):
#     await websocket.accept()

#     ticker_queue = asyncio.Queue()

#     try:
#         # Initial data
#         top_ten = await fetch_top_ten()

#         await websocket.send_json({
#             "type": "Top ten Coins Data",
#             # "channel": "TOP_TEN_INIT",
#             "data": top_ten,
#         })

#         product_ids = [coin["product_id"] for coin in top_ten]
#         asyncio.create_task(coinbase_ws_listener(product_ids, ticker_queue))

#         async def send_tickers():
#             while True:
#                 ticker = await ticker_queue.get()
#                 await websocket.send_json({
#                     "type": "Price Chart Data",
#                     "channel": "TICKER",
#                     "symbol": ticker["product_id"],
#                     "data": {
#                         "price": ticker["price"],
#                         "open_24h": ticker["open_24h"],
#                         "time": ticker["time"],
#                     },
#                 })

#         async def receive_messages():
#             print("📡 Waiting for client messages...")
#             while True:
#                 message = await websocket.receive_json()
#                 print("⬇️ Received:", message)

#                 if message.get("action") == "SELECT_SYMBOL":
#                     symbol = message["symbol"].upper()
#                     granularity = message.get("granularity", 900)

#                     candles = await fetch_candles(symbol, granularity)

#                     await websocket.send_json({
#                         "type": "Price Chart",
#                         "channel": "CANDLES",
#                         "symbol": candles["symbol"],
#                         "granularity": candles["granularity"],
#                         "data": candles["data"],
#                     })

#         # 🔥 RUN BOTH LOOPS TOGETHER
#         await asyncio.gather(
#             send_tickers(),
#             receive_messages(),
#         )

#     except WebSocketDisconnect:
#         print("❌ WebSocket disconnected")




# @router.websocket("/ws/crypto")
# async def crypto_socket(websocket: WebSocket):
#     await websocket.accept()
#     queue = asyncio.Queue()

#     try:
#         top_ten = await fetch_top_ten()

#         await websocket.send_json({
#             "type": "TOP_TEN_INIT",
#             "data": top_ten
#         })

#         product_ids = [coin["product_id"] for coin in top_ten]
#         asyncio.create_task(coinbase_ws_listener(product_ids, queue))

#         while True:
#             ticker = await queue.get()
#             await websocket.send_json({
#                 "type": "TICKER_UPDATE",
#                 "data": {
#                     "product_id": ticker["product_id"],
#                     "price": ticker["price"],
#                     "open_24h": ticker["open_24h"],
#                     "time": ticker["time"]
#                 }
#             })

#     except WebSocketDisconnect:
#         pass


# @router.get("/candles/{symbol}")
# async def get_price_chart(
#     symbol: str,
#     granularity: int = Query(3600)
# ):
#     product_id = f"{symbol.upper()}-USD"

#     url = (
#         settings.COINBASE_REST_URL
#         + settings.COINBASE_CANDLES_PATH.format(product_id=product_id)
#     )

#     async with httpx.AsyncClient(timeout=10) as client:
#         res = await client.get(url, params={"granularity": granularity})
#         res.raise_for_status()

#     candles = res.json()

#     return {
#         "symbol": product_id,
#         "granularity": granularity,
#         "data": [
#             {
#                 "time": c[0],
#                 "low": c[1],
#                 "high": c[2],
#                 "open": c[3],
#                 "close": c[4],
#                 "volume": c[5],
#             }
#             for c in candles
#         ]
#     }
