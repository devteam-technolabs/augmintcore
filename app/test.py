# import ccxt
# import json
# import asyncio
# import functools
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Security
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select

# from app.models.user import User
# from app.db import get_async_session
# from app.auth import auth_user

# router = APIRouter()

# exchange = ccxt.coinbaseexchange({
#     "apiKey": "76d97f29a7dba9afae61da53abdc172e",
#     "secret": "h3xlRF1bpXKrZM6I03Q4hTn1vw7por2rUM7vL+MK75PW9l3AnY6u/bJZvW30vOCeo81PvN+Mm/RhGjPcpXrJIQ==",
#     "password": "5gzc1ji04g2v",
#     "enableRateLimit": True,
# })

# symbol = "BTC/USD"


# async def fetch_orderbook_async(symbol:str, user=None, db=None):
#     keys = await get_keys("coinbase", user.id, db)

#     exchange = ccxt.coinbaseexchange({
#         "apiKey": keys["api_key"],
#         "secret": keys["api_secret"],
#         "password": keys["passphrase"],
#         "enableRateLimit": True,
#     })
#     loop = asyncio.get_running_loop()
#     return await loop.run_in_executor(
#         None, functools.partial(exchange.fetch_order_book, symbol)
#     )


# @router.websocket("/ws/orderbook/{exchange_name}")
# async def user_orderbook_stream(
#     websocket: WebSocket,
#     exchange_name: str,
#     db: AsyncSession = Depends(get_async_session),
#     current_user: User = Security(auth_user.get_current_user),
# ):

#     await websocket.accept()

#     # Validate user
#     result = await db.execute(select(User).where(User.id == current_user.id))
#     user = result.scalar_one_or_none()

#     if not user:
#         await websocket.send_text(json.dumps({"error": "User not found"}))
#         await websocket.close()
#         return

#     print(f"📡 User {user.id} connected to orderbook stream")

#     try:
#         while True:
#             # Non-blocking ccxt
#             orderbook = await fetch_orderbook_async(symbol)

#             bids = orderbook["bids"][:10]
#             asks = orderbook["asks"][:10]

#             payload = {
#                 "exchange": exchange_name,
#                 "user_id": user.id,
#                 "bids": [{"price": b[0], "size": b[1]} for b in bids],
#                 "asks": [{"price": a[0], "size": a[1]} for a in asks],
#             }

#             await websocket.send_text(json.dumps(payload))
#             await asyncio.sleep(1)

#     except WebSocketDisconnect:
#         print(f"🔌 User {user.id} disconnected")

#     except Exception as e:
#         print("❌ Unexpected WebSocket error:", e)

#     finally:
#         try:
#             await websocket.close()
#         except:
#             pass


# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)
