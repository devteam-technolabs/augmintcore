import asyncio
import json
import logging

from app.core.redis import redis_client
from app.coinbase.exchange import calculate_dashboard
from app.db.session import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select

logger = logging.getLogger(__name__)

DASHBOARD_REFRESH = 30  # seconds


async def dashboard_worker():
    """
    Background task that refreshes dashboard cache
    for all active users every 30 seconds.
    """

    logger.info("🚀 Dashboard worker started")

    while True:
        try:
            async with AsyncSessionLocal() as db:

                result = await db.execute(select(User))
                users = result.scalars().all()

                logger.info(f"📊 Updating dashboard for {len(users)} users")

                for user in users:

                    try:
                        dashboard = await calculate_dashboard(
                            "coinbase",
                            user,
                            db,
                        )

                        redis_key = f"dashboard:{user.id}"

                        await redis_client.setex(
                            redis_key,
                            40,
                            json.dumps({
                                "data": dashboard
                            }),
                        )

                        logger.info(f"✅ Cached dashboard for user {user.id}")

                    except Exception as e:
                        logger.warning(
                            f"⚠️ Dashboard update failed for user {user.id}: {e}"
                        )

        except Exception as e:
            logger.error(f"🔥 Worker loop error: {e}")

        await asyncio.sleep(DASHBOARD_REFRESH)