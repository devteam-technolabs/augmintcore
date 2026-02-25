# import asyncio
# import json
# import logging

# from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.auth.user import get_user_from_token
# from app.db.session import get_async_session
# from app.websocket.handlers.market_price import handle_market_price, change_symbol
# from app.websocket.handlers.order_book import handle_order_book
# from app.websocket.handlers.top_10 import handle_top_10

# logger = logging.getLogger(__name__)
# router = APIRouter(prefix="/market", tags=["Market WebSocket"])

# DEFAULT_SYMBOL = "BTC-USD"


# @router.websocket("/ws")
# async def unified_market_ws(
#     websocket: WebSocket,
#     db: AsyncSession = Depends(get_async_session),
# ):
#     await websocket.accept()

#     # --- Auth: expect first message to be auth token ---
#     try:
#         auth_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
#         auth_data = json.loads(auth_msg)
#         token = auth_data.get("token")
#         if not token:
#             await websocket.send_json({"error": "Token required"})
#             await websocket.close()
#             return

#         user = await get_user_from_token(token, db)
#         if not user:
#             await websocket.send_json({"error": "Invalid token"})
#             await websocket.close()
#             return

#     except asyncio.TimeoutError:
#         await websocket.send_json({"error": "Auth timeout"})
#         await websocket.close()
#         return
#     except Exception as e:
#         await websocket.send_json({"error": str(e)})
#         await websocket.close()
#         return

#     user_id = str(user.id)
#     current_symbol = DEFAULT_SYMBOL

#     # Active background tasks per session
#     active_tasks: dict[str, asyncio.Task] = {}

#     def cancel_task(name: str):
#         task = active_tasks.pop(name, None)
#         if task and not task.done():
#             task.cancel()

#     async def safe_send(data: dict):
#         try:
#             await websocket.send_json(data)
#         except Exception:
#             pass

#     logger.info(f"User {user_id} connected to unified WS")

#     try:
#         async for raw_msg in websocket.iter_text():
#             try:
#                 msg = json.loads(raw_msg)
#             except json.JSONDecodeError:
#                 await safe_send({"error": "Invalid JSON"})
#                 continue

#             msg_type = msg.get("type")
#             symbol = msg.get("symbol", current_symbol).upper()

#             # --- market_price ---
#             if msg_type == "subscribe_market_price":
#                 cancel_task("market_price")
#                 if symbol != current_symbol:
#                     current_symbol = symbol
#                     await change_symbol(user_id, current_symbol)
#                 active_tasks["market_price"] = asyncio.create_task(
#                     handle_market_price(websocket, user_id, current_symbol)
#                 )

#             # --- order_book ---
#             elif msg_type == "subscribe_order_book":
#                 cancel_task("order_book")
#                 current_symbol = symbol

#                 print("DEBUG: subscribe_order_book received")
#                 print("DEBUG: user_id:", user.id)
#                 print("DEBUG: symbol:", current_symbol)

#                 task = asyncio.create_task(
#                     handle_order_book(websocket, user.id, db, current_symbol)
#                 )

#                 def task_done_callback(t: asyncio.Task):
#                     try:
#                         exc = t.exception()
#                         if exc:
#                             print("❌ Order book task crashed with exception:", exc)
#                     except asyncio.CancelledError:
#                         print("⚠️ Order book task was cancelled")

#                 task.add_done_callback(task_done_callback)

#                 active_tasks["order_book"] = task

#             # --- top 10 ---
#             elif msg_type == "subscribe_top_10":
#                 cancel_task("top_10")
#                 active_tasks["top_10"] = asyncio.create_task(
#                     handle_top_10(websocket)
#                 )

#             # --- unsubscribe any ---
#             elif msg_type == "unsubscribe":
#                 category = msg.get("category")
#                 if category:
#                     cancel_task(category)
#                     await safe_send({"info": f"Unsubscribed from {category}"})

#             # --- change symbol across all active subscriptions ---
#             elif msg_type == "change_symbol":
#                 current_symbol = symbol
#                 if "market_price" in active_tasks:
#                     cancel_task("market_price")
#                     await change_symbol(user_id, current_symbol)
#                     active_tasks["market_price"] = asyncio.create_task(
#                         handle_market_price(websocket, user_id, current_symbol)
#                     )
#                 if "order_book" in active_tasks:
#                     cancel_task("order_book")
#                     active_tasks["order_book"] = asyncio.create_task(
#                         handle_order_book(websocket, user.id, db, current_symbol)
#                     )

#             else:
#                 await safe_send({"error": f"Unknown message type: {msg_type}"})

#     except WebSocketDisconnect:
#         logger.info(f"User {user_id} disconnected")

#     finally:
#         for task in active_tasks.values():
#             if not task.done():
#                 task.cancel()
#         logger.info(f"Cleaned up tasks for user {user_id}")

import asyncio
import json
import traceback
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.user import get_user_from_token
from app.db.session import get_async_session
from app.websocket.handlers.market_price import handle_market_price

router = APIRouter(prefix="/market")

DEFAULT_SYMBOL = "BTC-USD"


@router.websocket("/ws")
async def unified_market_ws(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_async_session),
):
    print("🔵 WebSocket connection attempt")

    await websocket.accept()
    print("✅ WebSocket accepted")

    # 🔥 KEEP ALIVE TASK
    async def keep_alive():
        while True:
            await asyncio.sleep(20)
            try:
                print("💓 Sending ping to client")
                await websocket.send_json({"type": "ping"})
            except Exception:
                print("❌ Ping failed — client disconnected?")
                break

    asyncio.create_task(keep_alive())

    try:
        auth_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        print("📩 Auth message:", auth_msg)

        auth_data = json.loads(auth_msg)
        token = auth_data.get("token")

        user = await get_user_from_token(token, db)

        if not user:
            print("❌ Invalid token")
            await websocket.close()
            return

    except Exception as e:
        print("🔥 Auth error:", e)
        traceback.print_exc()
        await websocket.close()
        return

    user_id = str(user.id)
    print("🟢 User connected:", user_id)

    try:
        async for raw_msg in websocket.iter_text():
            print("📨 Message from client:", raw_msg)

            msg = json.loads(raw_msg)

            if msg.get("type") == "subscribe_market_price":
                symbol = msg.get("symbol", DEFAULT_SYMBOL)
                print("📈 Subscribing to market price:", symbol)

                asyncio.create_task(
                    handle_market_price(websocket, user_id, symbol)
                )

    except WebSocketDisconnect:
        print("🔴 WebSocketDisconnect triggered")

    except Exception as e:
        print("🔥 WebSocket error:", e)
        traceback.print_exc()

    finally:
        print("🔴 WebSocket closed")

        # cancel market_price worker for this user
        from app.websocket.background.coinbase_worker import active_workers

        worker_task = active_workers.pop(user_id, None)
        if worker_task and not worker_task.done():
            print("🛑 Cancelling CoinbaseWorker for user:", user_id)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                print("✅ Worker cancelled successfully")