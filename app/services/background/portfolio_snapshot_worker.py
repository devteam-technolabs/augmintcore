import asyncio
import logging

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User,PortfolioSnapshot
from app.coinbase.exchange import get_keys
from app.coinbase.coinbase_cctx import get_working_coinbase_exchange

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL = 86400  # 24 hours


async def portfolio_snapshot_worker():

    logger.info("🚀 Portfolio snapshot worker started")

    try:
        while True:

            print("\n📊 RUNNING PORTFOLIO SNAPSHOT TASK")

            async with AsyncSessionLocal() as db:

                users_result = await db.execute(select(User))
                users = users_result.scalars().all()

                print("TOTAL USERS:", len(users))

                for user in users:

                    exchange = None

                    try:
                        keys = await get_keys(
                            exchange_name="coinbase",
                            user_id=user.id,
                            db=db,
                        )

                        if not keys:
                            print(f"No exchange keys for user {user.id}")
                            continue

                        exchange = await get_working_coinbase_exchange(
                            keys["api_key"],
                            keys["api_secret"],
                            keys.get("passphrase", ""),
                        )

                        balance = getattr(
                            exchange,
                            "_cached_validation_balance",
                            None,
                        )

                        if not balance:
                            continue

                        total_assets_balance = balance["total"]

                        STABLE_COINS = {"USDC", "USDT"}

                        portfolio_value = 0.0

                        for asset, amount in total_assets_balance.items():

                            if amount == 0:
                                continue

                            if asset in STABLE_COINS:
                                usd_value = amount
                            else:
                                symbol = f"{asset}/USD"

                                ticker = await exchange.fetch_ticker(symbol)
                                usd_value = amount * ticker["last"]

                            portfolio_value += usd_value

                        snapshot = PortfolioSnapshot(
                            user_id=user.id,
                            portfolio_value=portfolio_value,
                        )

                        db.add(snapshot)

                    except Exception as e:
                        print(f"Error processing user {user.id}: {e}")

                    finally:
                        if exchange:
                            await exchange.close()

                await db.commit()

            print("✅ Portfolio snapshot completed")

            await asyncio.sleep(SNAPSHOT_INTERVAL)

    except asyncio.CancelledError:
        logger.info("🛑 Portfolio snapshot worker stopped")
        raise