import json
import asyncio
import websockets
from app.core.config import get_settings

settings = get_settings()


import httpx
import logging
logger = logging.getLogger(__name__)

async def coinbase_ws_listener(product_ids: list[str], queue: asyncio.Queue):
    """
    Listens to Coinbase WebSocket for real-time ticker updates.
    """
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


# New helper functions for new requirement
async def fetch_coinbase_stats(product_id: str):
    """
    Fetches 24-hour stats for a product from Coinbase REST API.
    Provides open, high, low, and volume.
    """
    url = f"{settings.COINBASE_REST_URL}/products/{product_id}/stats"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
            res.raise_for_status()
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching Coinbase stats for {product_id}: {e}")
        return None

async def fetch_coinbase_products():
    """
    Fetches all available products from Coinbase to determine 'top' coins.
    Note: Coinbase doesn't provide ranking by market cap. 
    We will fallback to a prioritized list of popular USD pairs.
    """
    url = f"{settings.COINBASE_REST_URL}/products"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
            res.raise_for_status()
            products = res.json()
            # Filter for USD pairs and active products
            usd_products = [p for p in products if p['quote_currency'] == 'USD' and not p.get('cancel_only')]
            return usd_products
    except Exception as e:
        logger.error(f"Error fetching Coinbase products: {e}")
        return []

