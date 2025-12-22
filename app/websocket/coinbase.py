import json
import asyncio
import websockets
from app.core.config import get_settings

settings = get_settings()


async def coinbase_ws_listener(product_ids: list[str], queue: asyncio.Queue):
    async with websockets.connect(settings.COINBASE_WS_URL) as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "product_ids": product_ids,
            "channels": ["ticker"]
        }))

        async for message in ws:
            data = json.loads(message)
            if data.get("type") == "ticker":
                await queue.put(data)
