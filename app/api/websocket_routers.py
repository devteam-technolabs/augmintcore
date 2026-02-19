import asyncio
import json
import logging

import websockets
from fastapi import APIRouter, Depends, Query, Security, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.user import auth_user
from app.coinbase.exchange import fetch_orderbook_async
from app.core.config import get_settings
from app.db.session import get_async_session
from app.models.user import User

settings = get_settings()
router = APIRouter(prefix="/market", tags=["Market"])
logger = logging.getLogger(__name__)

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

TOP_10_PRODUCTS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "BNB-USD",
    "XRP-USD",
    "ADA-USD",
    "DOGE-USD",
    "AVAX-USD",
    "LINK-USD",
    "MATIC-USD",
]

TIMEFRAME_MAP = settings.TIMEFRAME_MAP


# Webscokets for getting the data of top ten crypto currencies###
price_store: dict[str, dict] = {}
_shutdown_event = asyncio.Event()


async def coinbase_ws_listener():
    print("coinbase listener started")
    while not _shutdown_event.is_set():
        try:
            async with websockets.connect(COINBASE_WS_URL) as ws:
                print("connected to coinbase")
                subscribe_message = {
                    "type": "subscribe",
                    "channels": [{"name": "ticker", "product_ids": TOP_10_PRODUCTS}],
                }

                await ws.send(json.dumps(subscribe_message))
                print("subscribd to coinbase ")
                async for msg in ws:

                    data = json.loads(msg)
                    # print(data)

                    if data.get("type") == "ticker":
                        data["symbol"] = data["product_id"]
                        price_store.update(data)

        except Exception as e:
            await asyncio.sleep(5)


async def stop_coinbase_ws():
    _shutdown_event.set()


# async def coinbase_single_symbol_ws(symbol: str, client_ws: WebSocket):
#     last_sent = 0
#     SEND_INTERVAL = 2.5

#     try:
#         async with websockets.connect(COINBASE_WS_URL, ping_interval=20) as cb_ws:
#             await cb_ws.send(
#                 json.dumps(
#                     {
#                         "type": "subscribe",
#                         "channels": [
#                             {
#                                 "name": "ticker",
#                                 "product_ids": [symbol],
#                             }
#                         ],
#                     }
#                 )
#             )

#             async for msg in cb_ws:
#                 data = json.loads(msg)

#                 if data.get("type") != "ticker":
#                     continue

#                 now = asyncio.get_event_loop().time()

#                 if now - last_sent >= SEND_INTERVAL:
#                     data["symbol"] = data["product_id"]
#                     await client_ws.send_json(data)
#                     last_sent = now

#     except Exception as e:
#         logger.error(f"Coinbase WS error ({symbol}): {e}")


@router.websocket("/ws/top10")
async def top10_prices(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json({"type": "prices", "data": price_store})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


@router.websocket("/order/book")
async def user_orderbook_stream(
    websocket: WebSocket,
    symbol: str = Query(...),
    token: str = Query(...),
    db: AsyncSession = Depends(get_async_session),
):
    print("WebSocket connection request received")
    await websocket.accept()
    try:
        from jose import JWTError, jwt

        from app.core.config import get_settings

        settings = get_settings()

        payload = jwt.decode(
            token, settings.ACCESS_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("user_id")
        if not user_id:
            raise Exception("Invalid token")

        user = await db.get(User, int(user_id))
        if not user:
            raise Exception("User not found")

    except Exception as e:
        await websocket.send_text(json.dumps({"error": str(e)}))
        await websocket.close()
        return

    print(f"📡 User {user.id} connected to orderbook stream")

    try:
        exchange = await fetch_orderbook_async(symbol, user=user, db=db)
        while True:
            try:
                orderbook = await exchange.fetch_order_book(symbol)

                bids = orderbook["bids"][:10]
                asks = orderbook["asks"][:10]

                payload = {
                    "bids": [{"price": b[0], "size": b[1]} for b in bids],
                    "asks": [{"price": a[0], "size": a[1]} for a in asks],
                }

                await websocket.send_text(json.dumps(payload))
                await asyncio.sleep(2)
            finally:
                await exchange.close()

    except WebSocketDisconnect:
        print(f"🔌 User {user.id} disconnected")

    finally:
        await websocket.close()


# @router.websocket("/ws/price/{symbol}")
# async def single_coin_stream(ws: WebSocket, symbol: str):
#     await ws.accept()
#     symbol = symbol.upper()

#     logger.info(f"Client connected for {symbol}")

#     try:
#         await coinbase_single_symbol_ws(symbol, ws)

#     except WebSocketDisconnect:
#         logger.info(f"Client disconnected ({symbol})")

#     except Exception as e:
#         logger.error(f"WS error ({symbol}): {e}")

#     finally:
#         await ws.close()

SEND_INTERVAL = 2.5

class CoinbaseClient:
    def __init__(self, symbol: str, client_ws: WebSocket):
        self.symbol = symbol
        self.client_ws = client_ws
        self.last_sent = 0

    async def connect_and_stream(self):
        while True:
            try:
                logger.info(f"Connecting to Coinbase WS for {self.symbol}")
                async with websockets.connect(
                    COINBASE_WS_URL,
                    ping_interval=10,
                    ping_timeout=30
                ) as cb_ws:

                    # subscribe to ticker + heartbeats
                    await cb_ws.send(
                        json.dumps({
                            "type": "subscribe",
                            "channels": [
                                {"name": "ticker", "product_ids": [self.symbol]},
                                {"name": "heartbeats", "product_ids": [self.symbol]},
                            ],
                        })
                    )

                    async for message in cb_ws:
                        data = json.loads(message)

                        # ignore everything that isn't a ticker update
                        if data.get("type") != "ticker":
                            continue

                        now = asyncio.get_event_loop().time()
                        if now - self.last_sent >= SEND_INTERVAL:
                            data["symbol"] = data["product_id"]
                            await self.client_ws.send_json(data)
                            self.last_sent = now

            except websockets.exceptions.ConnectionClosedError as e:
                logger.warning(f"Coinbase WS closed: {self.symbol} — reopening: {e}")

            except Exception as e:
                logger.error(f"Unexpected error for {self.symbol}: {e}")

            # small delay before reconnecting
            await asyncio.sleep(1)


@router.websocket("/ws/price/{symbol}")
async def single_coin_stream(ws: WebSocket, symbol: str):
    await ws.accept()
    symbol = symbol.upper()

    logger.info(f"Client connected for {symbol}")

    try:
        client = CoinbaseClient(symbol, ws)
        await client.connect_and_stream()

    except WebSocketDisconnect:
        logger.info(f"Client disconnected ({symbol})")

    except Exception as e:
        logger.error(f"WS error ({symbol}): {e}")

    finally:
        try:
            await ws.close()
        except:
            pass

from app.core.redis import redis_client
from app.websocket.manager import manager
from app.workers.coinbase_worker import CoinbaseWorker

def fake_auth(websocket: WebSocket):
    # Replace with real JWT validation
    return websocket.query_params.get("user_id")

# @router.websocket("/ws/dashboard/")
# async def dashboard_ws(websocket: WebSocket):
#     await websocket.accept()

#     user_id = fake_auth(websocket)
#     if not user_id:
#         await websocket.close()
#         return

#     await manager.connect(user_id, websocket)

#     pubsub = redis_client.pubsub()
#     await pubsub.subscribe(f"user:{user_id}")

#     try:
#         async for message in pubsub.listen():
#             if message['type'] == "message":
#                 data = json.loads(message['data'])
#                 await websocket.send_json(data)
#     except WebSocketDisconnect:
#         manager.disconnect(user_id)
#     finally:
#         await pubsub.unsubscribe(f"user:{user_id}")
#         await pubsub.close()


active_workers = {}  # prevent duplicate workers


@router.websocket("/ws/price/{symbol}")
async def dashboard_ws(websocket: WebSocket, symbol: str):
    await websocket.accept()

    user_id = "1"   # STATIC for testing
    symbol = symbol.upper()

    # Start worker if not already running
    if user_id not in active_workers:
        worker = CoinbaseWorker(user_id=user_id, symbol=symbol)
        task = asyncio.create_task(worker.start())
        active_workers[user_id] = task

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"user:{user_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)

    except WebSocketDisconnect:
        print("Client disconnected")

    finally:
        await pubsub.unsubscribe(f"user:{user_id}")
        await pubsub.close()



