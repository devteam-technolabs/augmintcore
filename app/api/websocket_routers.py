from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import time
import math
import logging
from datetime import datetime, timezone

from app.websocket.coingecko import fetch_top_ten, fetch_top_ten_v2, fetch_coin_details
from app.websocket.coinbase import (
    coinbase_ws_listener, 
    fetch_coinbase_stats, 
    fetch_coinbase_products
)
from app.websocket.coinmarketcap import fetch_cmc_details, fetch_top_ten_cmc
from app.core.config import get_settings
from app.websocket.candels import fetch_candles, fetch_candles_v2

settings = get_settings()
router = APIRouter(prefix="/market", tags=["Market"])
logger = logging.getLogger(__name__)

# --- Configuration & Helpers (New Code) ---

TIMEFRAME_MAP = settings.TIMEFRAME_MAP

def calculate_volatility(candles, window=24):
    """Calculates realized volatility from log returns of candles."""
    if not candles or len(candles) < 2:
        return 0
    subset = candles[:window+1]
    log_returns = []
    for i in range(len(subset) - 1):
        p1, p2 = float(subset[i]["close"]), float(subset[i+1]["close"])
        if p2 > 0:
            log_returns.append(math.log(p1 / p2))
    if len(log_returns) < 2:
        return 0
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean)**2 for r in log_returns) / (len(log_returns) - 1)
    return math.sqrt(variance) * 100

def format_currency_short(value):
    """Formats large financial numbers (T, B, M)."""
    if not value or value == 0:
        return "N/A"
    try:
        val = float(value)
    except:
        return "N/A"
    if val >= 1e12: return f"${val/1e12:.2f}T"
    if val >= 1e9:  return f"${val/1e9:.2f}B"
    if val >= 1e6:  return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"


# =====================================================
# 🔹 OLD CODE WEBSET SERVICE
# =====================================================

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


# =====================================================
# 🔹 NEW CODE WEBSET SERVICE (Requirement Version 2)
# =====================================================

@router.websocket("/ws/crypto/v2")
@router.websocket("/ws/crypto/v2/")
async def crypto_socket_v2(websocket: WebSocket):
    await websocket.accept()

    symbol_param = websocket.query_params.get("symbol")
    timeframe_param = websocket.query_params.get("timeframe", "1S")

    ticker_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    tasks: list[asyncio.Task] = []

    try:
        # ==========================
        # 🟢 DASHBOARD MODE
        # ==========================
        if symbol_param:
            state = {
                "symbol": symbol_param.upper(),
                "product_id": f"{symbol_param.upper()}-USD",
                "timeframe": timeframe_param,
                "granularity": TIMEFRAME_MAP.get(timeframe_param, 60),
                "details": None,
                "historical_candles": [],
                "volatility": 0.0,
                "anchor": 1.0,
                "active": True,
                "sparkline_sent": False,
            }

            # 🔁 SINGLE Coinbase WS Listener (IMPORTANT FIX)
            coinbase_task = asyncio.create_task(
                coinbase_ws_listener([state["product_id"]], ticker_queue)
            )
            tasks.append(coinbase_task)

            async def sync_market_data():
                """Low-frequency REST sync (every 5s)"""
                while state["active"]:
                    try:
                        details = await fetch_cmc_details(state["symbol"])
                        if details:
                            state["details"] = details

                        candles = await fetch_candles_v2(
                            state["symbol"], state["granularity"]
                        )
                        if candles:
                            state["historical_candles"] = candles
                            state["volatility"] = calculate_volatility(candles)

                            if details:
                                cb_price = float(candles[0]["close"])
                                cmc_price = float(details["price"])
                                if cb_price > 0:
                                    state["anchor"] = cmc_price / cb_price

                    except Exception as e:
                        logger.error(f"Market sync error: {e}")

                    await asyncio.sleep(5)

            async def stream_dashboard_updates():
                """High-frequency WS stream"""
                while state["active"]:
                    ticker = await ticker_queue.get()

                    if ticker.get("product_id") != state["product_id"]:
                        continue

                    details = state["details"]
                    if not details:
                        continue

                    live_price = float(ticker["price"]) * state["anchor"]

                    vol_24h = float(details.get("volume_24h", 0))
                    market_cap = float(details.get("market_cap", 0))
                    fdv = float(details.get("fdv", 0))

                    vol_mkt_cap_ratio = (
                        (vol_24h / market_cap) * 100 if market_cap else 0
                    )

                    open_24h = (
                        float(details["price"])
                        / (1 + details.get("price_change_24h", 0) / 100)
                        if details.get("price_change_24h") is not None
                        else live_price
                    )

                    change_24h = (
                        ((live_price - open_24h) / open_24h) * 100
                        if open_24h
                        else 0
                    )

                    payload = {
                        "type": "dashboard_data",
                        "symbol": state["product_id"],
                        "timeframe": state["timeframe"],
                        "change": f"{change_24h:.4f}",
                        "price_chart": {
                            "price": f"{live_price:.2f}",
                            "high": f"{float(details.get('high_24h', 0)):.2f}",
                            "low": f"{float(details.get('low_24h', 0)):.2f}",
                            "volume": f"{vol_24h:.2f}",
                            "time_iso": datetime.now(timezone.utc).isoformat(),
                        },
                        "portfolio_volatility_chart": {
                            "volatility": f"{state['volatility']:.2f}",
                            "time_iso": datetime.now(timezone.utc).isoformat(),
                        },
                        "stats": {
                            "Volume (24h)": format_currency_short(vol_24h),
                            "vol_mkt_cap_ratio": f"{vol_mkt_cap_ratio:.2f}%",
                            "fdv": format_currency_short(fdv),
                            "market_cap": format_currency_short(market_cap),
                        },
                    }

                    # 🟡 SEND SPARKLINE ONCE (500 POINTS)
                    if not state["sparkline_sent"] and state["historical_candles"]:
                        candles = state["historical_candles"][:500]

                        payload["price_chart"]["sparkline"] = [
                            {
                                "time": c["time"],
                                "price": f"{float(c['close']) * state['anchor']:.2f}",
                            }
                            for c in candles
                        ]

                        payload["portfolio_volatility_chart"]["sparkline"] = [
                            {
                                "time": c["time"],
                                "val": f"{float(c['close']) * state['anchor']:.2f}",
                            }
                            for c in candles
                        ]

                        state["sparkline_sent"] = True

                    await websocket.send_json(payload)

            async def handle_commands():
                """Client commands (symbol/timeframe change)"""
                while state["active"]:
                    msg = await websocket.receive_json()
                    action = msg.get("action")

                    if action == "CHANGE_SYMBOL":
                        new_symbol = msg.get("symbol", "BTC").upper()
                        if new_symbol != state["symbol"]:
                            state.update({
                                "symbol": new_symbol,
                                "product_id": f"{new_symbol}-USD",
                                "sparkline_sent": False,
                            })

                    elif action == "CHANGE_TIMEFRAME":
                        tf = msg.get("timeframe")
                        if tf in TIMEFRAME_MAP:
                            state["timeframe"] = tf
                            state["granularity"] = TIMEFRAME_MAP[tf]
                            state["sparkline_sent"] = False

            tasks.extend([
                asyncio.create_task(sync_market_data()),
                asyncio.create_task(stream_dashboard_updates()),
                asyncio.create_task(handle_commands()),
            ])

            await asyncio.gather(*tasks)

        # ==========================
        # 🔵 TOP TEN MODE
        # ==========================
        else:
            top_ten = await fetch_top_ten_cmc()
            product_ids = [coin["product_id"] for coin in top_ten]

            await websocket.send_json({
                "type": "Top Ten Coins",
                "data": top_ten
            })

            coinbase_task = asyncio.create_task(
                coinbase_ws_listener(product_ids, ticker_queue)
            )
            tasks.append(coinbase_task)

            while True:
                ticker = await ticker_queue.get()
                pid = ticker["product_id"]
                price = float(ticker["price"])
                open_24h = float(ticker.get("open_24h", price))
                change = (price - open_24h) / open_24h if open_24h else 0

                await websocket.send_json({
                    "type": "Top Ten Update",
                    "symbol": pid.split("-")[0],
                    "product_id": pid,
                    "price": f"{price:.2f}",
                    "change": f"{change:.4f}",
                    "time": datetime.now(timezone.utc).isoformat(),
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        for task in tasks:
            task.cancel()
        try:
            await websocket.close()
        except:
            pass
