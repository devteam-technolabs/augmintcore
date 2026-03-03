import asyncio
import logging

from fastapi import WebSocket

from app.websocket.background.top10_listener import price_store

logger = logging.getLogger(__name__)

PUSH_INTERVAL = 1  # seconds


async def handle_top_10(websocket: WebSocket):
    """
    Pushes current top-10 prices to connected client every second.
    Data is sourced from in-memory price_store populated by top10_listener.
    """
    while True:
        payload = {
            "category": "market_top_10",
            "data": list(price_store.values()),
        }
        await websocket.send_json(payload)
        await asyncio.sleep(PUSH_INTERVAL)
