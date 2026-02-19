import json
import asyncio
import logging
import random
import websockets
from app.core.redis import redis_client

logger = logging.getLogger("uvicorn.error")

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"


class CoinbaseWorker:

    def __init__(self, user_id: str, symbol: str):
        self.user_id = user_id
        self.symbol = symbol
        self.redis_channel = f"user:{user_id}"

    async def start(self):
        backoff = 1

        while True:
            try:
                logger.info(f"Connecting Coinbase for user {self.user_id}")

                async with websockets.connect(
                    COINBASE_WS_URL,
                    ping_interval=10,
                    ping_timeout=30
                ) as ws:

                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "channels": [
                            {"name": "ticker", "product_ids": [self.symbol]},
                            {"name": "heartbeats", "product_ids": [self.symbol]},
                        ],
                    }))

                    backoff = 1  # reset on success

                    async for message in ws:
                        data = json.loads(message)

                        if data.get("type") != "ticker":
                            continue

                        data["symbol"] = data["product_id"]

                        # publish to Redis
                        await redis_client.publish(
                            self.redis_channel,
                            json.dumps(data)
                        )

            except Exception as e:
                logger.warning(f"Coinbase worker error: {e}")

            # exponential backoff
            await asyncio.sleep(min(backoff, 30))
            backoff *= 2
