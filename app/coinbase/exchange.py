# -----------------------------------------
# Standard Library Imports
# -----------------------------------------
import asyncio
import functools
import json
import math
from datetime import datetime, timedelta, timezone

# -----------------------------------------
# Third-Party Imports
# -----------------------------------------
import ccxt.async_support as ccxt
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.user import auth_user
from app.coinbase.coinbase_cctx import get_working_coinbase_exchange

# -----------------------------------------
# Local Application Imports
# -----------------------------------------
from app.db.session import get_async_session
from app.models.user import ExchangeOrder, User, UserExchange
from app.security.kms_service import kms_service

TIMEFRAME_RULES = {
    "1m": {"tf": "1m", "max_days": 30},
    "15m": {"tf": "15m", "max_days": 90},
    "1h": {"tf": "1h", "max_days": 180},
    "1d": {"tf": "1d", "max_days": 365},
    "1w": {"tf": "1w", "max_days": 1095},
}

PERIOD_MAP = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
}


CRYPTO_NAME_MAP = {
    "bitcoin": "BTC/USD",
    "ethereum": "ETH/USD",
    "solana": "SOL/USD",
    "bnb": "BNB/USD",
    "ripple": "XRP/USD",
    "cardano": "ADA/USD",
    "dogecoin": "DOGE/USD",
    "avalanche-2": "AVAX/USD",
    "chainlink": "LINK/USD",
    "polygon": "POL/USD",
}


def clean_private_key(pem: str) -> str:
    return pem.replace("\\n", "\n").replace("\r", "").strip()


async def validate_coinbase_api(api_key: str, api_secret: str, passphrase: str) -> bool:
    exchange = None
    private_key = clean_private_key(api_secret)

    try:
        print("Trying Coinbase Advanced connection")
        exchange = ccxt.coinbaseadvanced(
            {
                "apiKey": api_key,
                "secret": private_key,  # raw secret
                "enableRateLimit": True,
            }
        )
        exchange.options["adjustForTimeDifference"] = True
        exchange.options["createMarketBuyOrderRequiresPrice"] = False

        await exchange.fetch_balance()
        return exchange

    except Exception as e:
        if exchange:
            try:
                await exchange.close()
            except:
                pass

    exchange = None
    try:

        exchange = ccxt.coinbaseexchange(
            {
                "apiKey": api_key.strip(),
                "secret": api_secret.strip(),
                "password": passphrase.strip(),
                "enableRateLimit": True,
            }
        )

        exchange.set_sandbox_mode(True)

        await exchange.fetch_balance()
        return exchange

    except ccxt.AuthenticationError as e:
        print("Coinbase authentication failed:", str(e))
        return False

    except Exception as e:
        print("Coinbase validation error:", str(e))
        return False

    finally:
        if exchange:
            try:
                await exchange.close()
            except:
                pass


async def safe_decrypt(value: str | None) -> str | None:
    if not value:
        return None

    try:
        # Try KMS decrypt
        return await kms_service.decrypt(value)

    except Exception:
        # 🔥 NOT KMS ENCRYPTED → assume plaintext
        return value


async def get_keys(
    exchange_name: str,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
):

    exchange_name = exchange_name.lower()

    result = await db.execute(
        select(UserExchange).where(
            UserExchange.user_id == user_id, UserExchange.exchange_name == exchange_name
        )
    )

    ex = result.scalar_one_or_none()

    if not ex:
        raise HTTPException(404, "No API keys found for this exchange")

    return {
        "exchange": exchange_name,
        "api_key": await safe_decrypt(ex.api_key),
        "api_secret": await safe_decrypt(ex.api_secret),
        "passphrase": await safe_decrypt(ex.passphrase),
        "created_at": ex.created_at,
    }


async def get_crypt_currencies(exchange_name: str, user, db):
    exchange = None

    try:
        # 🔑 Get decrypted keys
        user_keys = await get_keys(exchange_name, user.id, db)

        api_key = user_keys["api_key"]
        secret = user_keys["api_secret"]
        passphrase = user_keys["passphrase"]

        # ✅ CCXT Coinbase Exchange
        exchange = ccxt.coinbaseexchange(
            {
                "apiKey": api_key,
                "secret": secret,
                "password": passphrase,
                "enableRateLimit": True,
            }
        )

        # ✅ Sandbox mode
        exchange.set_sandbox_mode(True)

        # ✅ Load markets
        await exchange.load_markets()

        # 1️⃣ Fetch user balances (THIS decides which coins user owns)
        balance = await exchange.fetch_balance()

        # 2️⃣ Fetch tickers once
        tickers = await exchange.fetch_tickers()

        crypto_prices = []

        # 3️⃣ Iterate ONLY owned coins
        for currency, total_amount in balance["total"].items():

            if not total_amount or total_amount <= 0:
                continue

            asset_data = {
                "symbol": currency,
                "quantity": float(total_amount),
                "price_usd": None,
                "usd_value": None,
            }

            # USD case
            if currency == "USD":
                asset_data["price_usd"] = 1.0
                asset_data["usd_value"] = float(total_amount)

            # Crypto → USD
            else:
                pair = f"{currency}/USD"
                ticker = tickers.get(pair)

                if ticker and ticker.get("last"):
                    price = float(ticker["last"])
                    asset_data["price_usd"] = price
                    asset_data["usd_value"] = price * float(total_amount)

            # add only valid priced assets
            if asset_data["usd_value"] is not None:
                crypto_prices.append(asset_data)

        return crypto_prices

    except Exception as e:
        raise Exception(f"Failed to fetch crypto currencies: {str(e)}")

    finally:
        if exchange:
            await exchange.close()


async def user_portfolio_data(exchange_name: str, user, db):
    exchange = None

    try:
        # 🔑 Get decrypted keys
        usr_keys = await get_keys(exchange_name, user.id, db)

        api_key = usr_keys["api_key"]
        secret = usr_keys["api_secret"]
        passphrase = usr_keys["passphrase"]

        # ✅ Correct CCXT exchange
        exchange = ccxt.coinbaseexchange(
            {
                "apiKey": api_key,
                "secret": secret,
                "password": passphrase,
                "enableRateLimit": True,
            }
        )

        # ✅ Sandbox mode (VERY IMPORTANT)
        exchange.set_sandbox_mode(True)

        # ✅ Load markets once
        await exchange.load_markets()

        # 1️⃣ Fetch balances (Retry mechanism for robust auth)
        balance = None
        for i in range(2):
            try:
                balance = await exchange.fetch_balance()
                break
            except (ccxt.AuthenticationError, ccxt.ExchangeError) as e:
                if i == 0:
                    await asyncio.sleep(1.0)
                    continue
                raise e

        assets = []
        total_usd_value = 0.0

        # 2️⃣ Fetch tickers once
        tickers = await exchange.fetch_tickers()

        # 3️⃣ Iterate only real balances
        for currency, data in balance["total"].items():
            total_amount = data

            if not total_amount or total_amount <= 0:
                continue

            free = balance["free"].get(currency, 0)
            used = balance["used"].get(currency, 0)

            asset_data = {
                "asset": currency,
                "free": float(free),
                "locked": float(used),
                "total": float(total_amount),
                "usd_price": None,
                "usd_value": None,
            }

            # USD valuation
            if currency == "USD":
                asset_data["usd_price"] = 1.0
                asset_data["usd_value"] = float(total_amount)

            else:
                pair = f"{currency}/USD"
                ticker = tickers.get(pair)

                if ticker and ticker.get("last"):
                    price = float(ticker["last"])
                    asset_data["usd_price"] = price
                    asset_data["usd_value"] = price * float(total_amount)

            if asset_data["usd_value"]:
                total_usd_value += asset_data["usd_value"]

            assets.append(asset_data)

        return {
            "total_assets_value": round(total_usd_value, 2),
            "total_currencies": len(assets),
            "assets": assets,
        }

    except Exception as e:
        raise Exception(f"Failed to fetch user portfolio: {str(e)}")

    finally:
        if exchange:
            await exchange.close()


async def get_total_coin_value(exchange_name: str, user, db):
    exchange = None

    try:
        # 🔑 Get decrypted keys
        usr_keys = await get_keys(exchange_name, user.id, db)

        api_key = usr_keys["api_key"]
        secret = usr_keys["api_secret"]
        passphrase = usr_keys["passphrase"]

        # ✅ Correct Coinbase Exchange
        exchange = ccxt.coinbaseexchange(
            {
                "apiKey": api_key,
                "secret": secret,
                "password": passphrase,
                "enableRateLimit": True,
            }
        )

        # ✅ Sandbox mode
        exchange.set_sandbox_mode(True)

        await exchange.load_markets()

        # Fetch balances (Retry wrapper)
        balance = None
        for i in range(2):
            try:
                balance = await exchange.fetch_balance()
                break
            except (ccxt.AuthenticationError, ccxt.ExchangeError) as e:
                if i == 0:
                    await asyncio.sleep(1.0)
                    continue
                raise e
        tickers = await exchange.fetch_tickers()

        total_usd_value = 0.0
        currency_count = 0

        for currency, amount in balance["total"].items():
            if not amount or amount <= 0:
                continue

            currency_count += 1

            if currency == "USDC":
                total_usd_value += float(amount)
            else:
                pair = f"{currency}/USDC"
                ticker = tickers.get(pair)

                if ticker and ticker.get("last"):
                    total_usd_value += float(amount) * float(ticker["last"])

        return {
            "exchange": exchange_name,
            "total_coins_value": round(total_usd_value, 2),
            "currency_count": currency_count,
        }

    finally:
        if exchange:
            await exchange.close()


async def get_total_account_value(exchange_name: str, user, db):
    exchange = None

    try:
        keys = await get_keys(exchange_name, user.id, db)

        api_key = keys["api_key"]
        api_secret = keys["api_secret"]
        passphrase = keys.get("passphrase")

        exchange = await get_working_coinbase_exchange(
            api_key,
            api_secret,
            passphrase,
        )

        if not exchange:
            raise RuntimeError("No valid Coinbase exchange found")

        exchange.options["adjustForTimeDifference"] = True

        if hasattr(exchange, "_cached_validation_balance"):
            balance = exchange._cached_validation_balance
            print("🔄 Using cached authentication balance…", balance)
        else:
            balance = await exchange.fetch_balance()
            print("🔄 Testing authentication (fetch_balance)…", balance)

        return balance

    except Exception as e:

        print(f"❌ Failed to fetch account value: {e}")
        raise

    finally:

        if exchange:
            await exchange.close()


async def fetch_all_orders(exchange_name: str, symbol: str, user, db):
    exchange = None

    try:
        keys = await get_keys(exchange_name, user.id, db)
        api_key = keys["api_key"]
        api_secret = keys["api_secret"]
        passphrase = keys.get("passphrase")
        exchange = await get_working_coinbase_exchange(
            api_key,
            api_secret,
            passphrase,
        )
        if not exchange:
            raise RuntimeError("No valid Coinbase exchange found")
        exchange.options["adjustForTimeDifference"] = True
        orders = await exchange.fetch_orders(
            symbol=symbol, since=None, limit=200, params={"paginate": True}
        )
        return orders
    except Exception as e:
        print(f"❌ Failed to fetch account value: {e}")
        raise
    finally:
        if exchange:
            await exchange.close()


async def fetch_open_orders(exchange_name: str, symbol: str, user, db):
    exchange = None

    try:
        keys = await get_keys(exchange_name, user.id, db)
        api_key = keys["api_key"]
        api_secret = keys["api_secret"]
        passphrase = keys.get("passphrase")
        exchange = await get_working_coinbase_exchange(
            api_key,
            api_secret,
            passphrase,
        )
        if not exchange:
            raise RuntimeError("No valid Coinbase exchange found")
        exchange.options["adjustForTimeDifference"] = True
        orders = await exchange.fetchOpenOrders(
            symbol=symbol, since=None, limit=200, params={"paginate": True}
        )
        return orders
    except Exception as e:
        print(f"❌ Failed to fetch account value: {e}")
        raise
    finally:
        if exchange:
            await exchange.close()


async def fetch_close_orders(exchange_name: str, symbol: str, user, db):
    exchange = None

    try:
        keys = await get_keys(exchange_name, user.id, db)
        api_key = keys["api_key"]
        api_secret = keys["api_secret"]
        passphrase = keys.get("passphrase")
        exchange = await get_working_coinbase_exchange(
            api_key,
            api_secret,
            passphrase,
        )
        if not exchange:
            raise RuntimeError("No valid Coinbase exchange found")
        exchange.options["adjustForTimeDifference"] = True
        orders = await exchange.fetchClosedOrders(
            symbol=symbol, since=None, limit=200, params={"paginate": True}
        )
        return orders
    except Exception as e:
        print(f"❌ Failed to fetch account value: {e}")
        raise
    finally:
        if exchange:
            await exchange.close()


async def buy_sell_order_execution(
    symbol: str,
    side: str,
    quantity: float,  # base quantity (e.g. BTC)
    order_type: str,
    user,
    db,
    exchange_name: str,
    total_cost: float | None = None,
    exchange=None,
    limit_price=None,
):
    try:
        price = total_cost
        # ─────────────────────────────────────────────
        # 1. Load & validate exchange
        # ─────────────────────────────────────────────
        keys = await get_keys(exchange_name, user.id, db)
        print("keys", keys)

        exchange = await get_working_coinbase_exchange(
            keys["api_key"], keys["api_secret"], keys.get("passphrase", "")
        )
        print("exchange", exchange)

        if not exchange:
            raise RuntimeError("No valid Coinbase exchange found")

        exchange.options["adjustForTimeDifference"] = True

        side = side.lower()
        order_type = order_type.lower()

        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")

        if order_type not in {"market", "limit"}:
            raise ValueError("order_type must be market or limit")

        if order_type == "limit" and limit_price is None:
            raise ValueError("price required for limit orders")

        await exchange.load_markets()

        # ─────────────────────────────────────────────
        # 2. Fetch ticker for market orders
        # ─────────────────────────────────────────────
        ticker_price = None
        if order_type == "market":
            ticker = await exchange.fetch_ticker(symbol)
            ticker_price = ticker["last"]

        # ─────────────────────────────────────────────
        # 3. Balance-aware USD / USDC switching
        # ─────────────────────────────────────────────
        balance = (
            exchange._cached_validation_balance
            if hasattr(exchange, "_cached_validation_balance")
            else await exchange.fetch_balance()
        )

        base, quote = symbol.split("/")

        usd_free = balance.get("USD", {}).get("free", 0)
        usdc_free = balance.get("USDC", {}).get("free", 0)

        required_cost = None
        if order_type == "market" and side == "buy":
            required_cost = quantity * ticker_price * 1.01  # 1% buffer

            if (
                quote == "USD"
                and usd_free < required_cost
                and usdc_free >= required_cost
            ):
                alt_symbol = f"{base}/USDC"
                if alt_symbol in exchange.markets:
                    symbol = alt_symbol
                    quote = "USDC"

        exchange.options["createMarketBuyOrderRequiresPrice"] = False

        # Force USDC for market orders
        if exchange.id == "coinbaseadvanced" and order_type == "market":
            base, _ = symbol.split("/")
            usdc_symbol = f"{base}/USDC"
            if usdc_symbol in exchange.markets:
                symbol = usdc_symbol

        # ─────────────────────────────────────────────
        # 4. Create order (Coinbase-correct)
        # ─────────────────────────────────────────────
        params = {}
        print(
            f"Creating {order_type} order: {side} {quantity} {symbol} at price {price} (ticker price: {ticker_price})"
        )
        if order_type == "market":
            if side == "buy":
                # Coinbase requires quote_size, not base_size
                cost = quantity * ticker_price
                cost *= 0.995  # preview safety buffer

                print(
                    f"""
                    MARKET BUY
                    Symbol: {symbol}
                    Base qty: {quantity}
                    Price: {ticker_price}
                    Quote cost: {cost}
                    USD free: {usd_free}
                    USDC free: {usdc_free}
                    """
                )

                order = await exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=None,  # cost amount (USDC)
                    params={"cost": quantity},  # spend exactly 1 USDC
                )
            else:
                # market SELL uses base quantity
                order = await exchange.create_order(
                    symbol=symbol, type="market", side="sell", amount=quantity
                )
        elif order_type == "limit":
            if quantity is None or limit_price is None:
                raise ValueError("quantity and limit_price required")

            market = exchange.market(symbol)

            min_amount = market["limits"]["amount"]["min"]

            price = float(exchange.price_to_precision(symbol, limit_price))
            if side == "buy":
                base_amount = quantity / price
                total_btc = float(exchange.amount_to_precision(symbol, base_amount))
            else:
                total_btc = float(exchange.amount_to_precision(symbol, quantity))

            print(f"LIMIT ORDER → {side.upper()} {total_btc} {symbol} @ {price}")
            if total_btc < min_amount:
                raise ValueError(
                    f"Quantity too small. Min {symbol} size is {min_amount}"
                )
            order = await exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=total_btc,  # BASE quantity
                price=price,
                # LIMIT price (NOT total_cost)
            )

        # ─────────────────────────────────────────────
        # 5. Persist order
        # ─────────────────────────────────────────────
        new_order = ExchangeOrder(
            user_id=user.id,
            exchange_name=exchange_name.lower(),
            order_id=order.get("id"),
            client_order_id=order.get("clientOrderId"),
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            current_price=ticker_price or price,
            cost=order.get("cost"),
            status=order.get("status", "unknown"),
            raw_response=json.dumps(order),
        )

        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)

        return {
            "status": "success",
            "order_id": order.get("id"),
            "db_order_id": new_order.id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "price": price,
            "raw": order,
        }

    except Exception as e:
        print(f"❌ Order execution failed: {e}")
        raise

    finally:
        if exchange:
            await exchange.close()


async def get_profit_and_loss(exchange_name: str, user, db: AsyncSession):
    exchange = None

    try:
        keys = await get_keys(exchange_name, user.id, db)

        exchange = ccxt.coinbaseexchange(
            {
                "apiKey": keys["api_key"],
                "secret": keys["api_secret"],
                "password": keys["passphrase"],
                "enableRateLimit": True,
            }
        )

        exchange.set_sandbox_mode(True)
        await exchange.load_markets()

        balance = await exchange.fetch_balance()
        tickers = await exchange.fetch_tickers()

        total_portfolio_value = 0.0
        total_profit = 0.0
        total_loss = 0.0
        assets = []

        for currency, qty in balance["total"].items():
            if not qty or qty <= 0:
                continue

            # USD stays USD
            if currency == "USDC":
                usd_value = float(qty)
                total_portfolio_value += usd_value

                assets.append(
                    {
                        "asset": currency,
                        "quantity": float(qty),
                        "usd_value": round(usd_value, 2),
                    }
                )
                continue

            pair = f"{currency}/USDC"
            ticker = tickers.get(pair)
            if not ticker or not ticker.get("last"):
                continue

            current_price = float(ticker["last"])
            usd_value = current_price * float(qty)
            total_portfolio_value += usd_value

            # 🔥 BUY PRICE ASSUMPTION (Sandbox)
            buy_price = current_price * 0.90
            pnl = (current_price - buy_price) * float(qty)

            if pnl > 0:
                total_profit += pnl
            else:
                total_loss += abs(pnl)

            assets.append(
                {
                    "asset": currency,
                    "quantity": float(qty),
                    "buy_price": round(buy_price, 2),
                    "current_price": round(current_price, 2),
                    "usd_value": round(usd_value, 2),
                    "profit_or_loss": round(pnl, 2),
                }
            )

        return {
            "exchange": exchange_name,
            "status": "Coinbase_Sandbox",
            "total_portfolio_value_usd": round(total_portfolio_value, 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "assets": assets,
        }

    finally:
        if exchange:
            await exchange.close()


async def get_historical_data(
    user,
    timeframe: str,  # 1m, 15m, 1h, 1d, 1w
    period: str,  # 1m, 3m, 6m, 1y
    db: AsyncSession,
    symbol: str,
):
    target_symbol = CRYPTO_NAME_MAP.get(symbol.lower(), symbol.upper())
    user_id = user.id
    keys = await get_keys("coinbase", user_id, db)

    exchange = ccxt.coinbaseexchange(
        {
            "apiKey": keys["api_key"],
            "secret": keys["api_secret"],
            "password": keys["passphrase"],
        }
    )

    if timeframe not in TIMEFRAME_RULES:
        raise HTTPException(400, "Invalid timeframe")

    if period not in PERIOD_MAP:
        raise HTTPException(400, "Invalid period")

    tf_rule = TIMEFRAME_RULES[timeframe]
    requested_days = PERIOD_MAP[period]

    # Enforce safety limits
    days = min(requested_days, tf_rule["max_days"])

    since = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)

    all_ohlcv = []
    limit = 300
    since_copy = since

    while True:
        ohlcv = await exchange.fetch_ohlcv(
            target_symbol, timeframe=tf_rule["tf"], since=since_copy, limit=limit
        )

        if not ohlcv:
            break

        all_ohlcv.extend(ohlcv)
        print(
            f"Fetched {len(ohlcv)} candles, total so far: {len(all_ohlcv)}", all_ohlcv
        )
        since_copy = ohlcv[-1][0] + 1

        if ohlcv[-1][0] >= exchange.milliseconds():
            break

    df = pd.DataFrame(
        all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    return {
        "symbol": target_symbol,
        "timeframe": timeframe,
        "period": period,
        "days_returned": days,
        "candles": df.to_dict(orient="records"),
    }


TIMEFRAME_CONFIG = {
    "1m": {"days": 1, "candle_minutes": 1},
    "15m": {"days": 3, "candle_minutes": 15},
    "1h": {"days": 7, "candle_minutes": 60},
    "1d": {"days": 30, "candle_minutes": 1440},
}


async def fetch_from_binance(
    target_symbol,
    timeframe,
    since_timestamp,
    limit,
):
    exchange = ccxt.binance({"enableRateLimit": True})

    try:
        print("\n--- Trying exchange: binance ---")

        await exchange.load_markets()

        # Convert USD → USDT for Binance
        if target_symbol.endswith("/USD"):
            binance_symbol = target_symbol.replace("/USD", "/USDT")
        else:
            binance_symbol = target_symbol

        print("Converted Binance symbol:", binance_symbol)

        if binance_symbol not in exchange.symbols:
            print(f"❌ {binance_symbol} not supported on binance")
            return []

        candles = await exchange.fetch_ohlcv(
            binance_symbol,
            timeframe=timeframe,
            since=since_timestamp,
            limit=limit,
        )

        print(f"📊 Binance candles received: {len(candles)}")
        return candles

    except Exception as e:
        print("❌ Binance error:", str(e))
        return []

    finally:
        await exchange.close()
        print("binance connection closed")


async def fetch_from_exchange(
    exchange_class,
    target_symbol,
    timeframe,
    since_timestamp,
    limit,
    keys,
):
    exchange = exchange_class(
        {
            "apiKey": keys["api_key"],
            "secret": keys["api_secret"],
            "password": keys.get("passphrase"),
            "enableRateLimit": True,
        }
    )

    try:
        print(f"\n--- Trying exchange: {exchange_class.__name__} ---")

        await exchange.load_markets()

        if target_symbol not in exchange.symbols:
            print(f"❌ {target_symbol} not supported on {exchange_class.__name__}")
            return []

        print(f"✅ {target_symbol} supported on {exchange_class.__name__}")

        candles = await exchange.fetch_ohlcv(
            target_symbol,
            timeframe=timeframe,
            since=since_timestamp,
            limit=limit,
        )

        print(f"📊 Candles received: {len(candles)}")
        return candles

    except Exception as e:
        print(f"❌ Error from {exchange_class.__name__}: {str(e)}")
        return []

    finally:
        await exchange.close()
        print(f"{exchange_class.__name__} connection closed")


async def get_historical_ohlc_data(
    user,
    timeframe: str,
    symbol: str,
    before: int | None,
    db: AsyncSession,
):
    print("\n========== OHLC DEBUG START ==========")
    print("Requested coin:", symbol)
    print("Requested timeframe:", timeframe)

    if timeframe not in TIMEFRAME_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid timeframe")

    config = TIMEFRAME_CONFIG[timeframe]
    days = config["days"]
    candle_minutes = config["candle_minutes"]

    target_symbol = CRYPTO_NAME_MAP.get(symbol.lower(), symbol.upper())
    print("Mapped symbol:", target_symbol)

    keys = await get_keys("coinbase", user.id, db)

    # 🔒 Clamp timestamp safely
    temp_exchange = ccxt.coinbaseexchange()
    now = temp_exchange.milliseconds()
    await temp_exchange.close()

    if before:
        print("Before param:", before)
        until_timestamp = min(before, now)
    else:
        until_timestamp = now

    print("Final until timestamp:", until_timestamp)

    total_minutes = days * 24 * 60
    total_candles = total_minutes // candle_minutes
    limit = min(total_candles, 300)

    since_timestamp = until_timestamp - (limit * candle_minutes * 60 * 1000)

    print("Since timestamp:", since_timestamp)
    print("Limit:", limit)

    # 🔥 Try primary exchange first
    candles = await fetch_from_exchange(
        ccxt.coinbaseexchange,
        target_symbol,
        timeframe,
        since_timestamp,
        limit,
        keys,
    )

    # 🔁 Fallback if no data
    if not candles:
        print("No candles from coinbaseexchange. Trying binance...")
        candles = await fetch_from_binance(
            target_symbol,
            timeframe,
            since_timestamp,
            limit,
        )

    if not candles:
        print("⚠️ No candles from any exchange")
        print("========== OHLC DEBUG END ==========\n")
        return {
            "symbol": target_symbol,
            "timeframe": timeframe,
            "candles": [],
            "next_before": None,
        }

    formatted = [
        {
            "timestamp": datetime.fromtimestamp(
                c[0] / 1000, tz=timezone.utc
            ).isoformat(),
            "open": c[1],
            "high": c[2],
            "low": c[3],
            "close": c[4],
            "volume": c[5],
        }
        for c in candles
    ]

    next_before = candles[0][0]

    print("Oldest candle timestamp:", next_before)
    print("========== OHLC DEBUG END ==========\n")

    return {
        "symbol": target_symbol,
        "timeframe": timeframe,
        "candles": formatted,
        "next_before": next_before,
    }


async def get_volatility_data(symbol: str, user, db):

    keys = await get_keys("coinbase", user.id, db)

    exchange = ccxt.coinbaseexchange(
        {
            "apiKey": keys["api_key"],
            "secret": keys["api_secret"],
            "password": keys["passphrase"],
            "enableRateLimit": True,
        }
    )

    symbol = CRYPTO_NAME_MAP.get(symbol)

    # fetch 30 days of 1h candles → 720 candles
    ohlcv = await exchange.fetch_ohlcv(symbol, timeframe="1h", limit=720)
    await exchange.close()

    if not ohlcv or len(ohlcv) < 2:
        return {"symbol": symbol, "latest": None, "data": []}

    closes = [c[4] for c in ohlcv]
    timestamps = [c[0] for c in ohlcv]

    prices = np.array(closes)

    volatility_points = []

    # Compute volatility for every candle (cumulative)
    for i in range(2, len(prices)):  # start from index 2 because diff needs 2 points
        window = prices[:i]

        log_returns = np.diff(np.log(window))

        vol = np.std(log_returns) * math.sqrt(365 * 24)

        volatility_points.append(
            {"timestamp": timestamps[i], "volatility": round(float(vol), 6)}
        )

    return {
        "symbol": symbol,
        "latest": volatility_points[-1]["volatility"],
        "data": volatility_points,
    }


async def fetch_orderbook_async(symbol: str, user=None, db=None):
    keys = await get_keys("coinbase", user.id, db)

    exchange = ccxt.coinbaseexchange(
        {
            "apiKey": keys["api_key"],
            "secret": keys["api_secret"],
            "password": keys["passphrase"],
            "enableRateLimit": True,
        }
    )
    return exchange


async def get_real_profit_loss(
    exchange_name: str, user, db: AsyncSession, base_currency="USD"
):
    try:
        exchange = None

        keys = await get_keys(exchange_name, user.id, db)

        exchange = ccxt.coinbaseexchange(
            {
                "apiKey": keys["api_key"],
                "secret": keys["api_secret"],
                "password": keys["passphrase"],
                "enableRateLimit": True,
            }
        )

        balance = exchange.fetch_balance()
        holdings = {curr: amt for curr, amt in balance["total"].items() if amt > 0}
        total_portfolio_value = 0.0
        portfolio_value_24h_ago = 0.0

        for currency, amount in holdings.items():
            total_portfolio_value += amount
            portfolio_value_24h_ago += amount
            continue

        symbol = f"{currency}/{base_currency}"

        try:
            # Fetch 24h ticker data
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker["last"]
            open_price = ticker["open"]
            total_portfolio_value += amount * current_price
            if open_price:
                portfolio_value_24h_ago += amount * open_price
            else:
                # Fallback if 'open' isn't provided by the exchange
                portfolio_value_24h_ago += amount * current_price
        except ccxt.BadSymbol:
            print(f"Skipping {symbol} - not found on Coinbase.")
        except Exception as e:
            print(f"Error fetching ticker for {symbol}: {e}")
        pl_24h = total_portfolio_value - portfolio_value_24h_ago
        pl_24h_percentage = (
            (pl_24h / portfolio_value_24h_ago) * 100
            if portfolio_value_24h_ago > 0
            else 0
        )

        total_cost_basis = 0.0
        for currency in holdings.keys():
            if currency == base_currency:
                continue

            symbol = f"{currency}/{base_currency}"
            try:
                # Fetch historical trades for this specific pair
                trades = exchange.fetch_my_trades(symbol)

                for trade in trades:
                    if trade["side"] == "buy":
                        # Cost includes the fee
                        total_cost_basis += trade["cost"]
                    elif trade["side"] == "sell":
                        # Deduct proportional cost (simplified average method)
                        # More complex FIFO logic is needed for strict accounting
                        total_cost_basis -= trade["cost"]

            except Exception as e:
                print(f"Could not fetch trades for {symbol}: {e}")

            # 4. Calculate Total P/L
            total_pl = total_portfolio_value - total_cost_basis
            total_pl_percentage = (
                (total_pl / total_cost_basis) * 100 if total_cost_basis > 0 else 0
            )

            return {
                "Total Portfolio Value": round(total_portfolio_value, 2),
                "P/L 24h ($)": round(pl_24h, 2),
                "P/L 24h (%)": round(pl_24h_percentage, 2),
                "Cost Basis": round(total_cost_basis, 2),
                "Total P/L ($)": round(total_pl, 2),
                "Total P/L (%)": round(total_pl_percentage, 2),
            }

    except ccxt.NetworkError as e:
        print(f"Network error: {e}")
    except ccxt.ExchangeError as e:
        print(f"Exchange error: {e}")


async def calculate_dashboard(exchange_name: str, user, db: AsyncSession):
    exchange = None
    keys = await get_keys(exchange_name, user.id, db)

    try:
        exchange = await get_working_coinbase_exchange(
            keys["api_key"], keys["api_secret"], keys.get("passphrase", "")
        )

        balance = (
            exchange._cached_validation_balance
            if hasattr(exchange, "_cached_validation_balance")
            else await exchange.fetch_balance()
        )
        total_assets_balance = balance["total"]
        STABLE_COINS = {"USDC", "USDT"}
        # tickers = await exchange.fetch_ticker()
        portfolio_value = 0.0
        total_cost_basis = 0.0
        asset_breakdown = {}
        asset_amount = {}

        for asset, amount in total_assets_balance.items():
            if amount == 0:
                continue

            if asset in STABLE_COINS:
                usd_value = amount
            else:

                symbol = f"{asset}/USD"
                ticker = await exchange.fetch_ticker(symbol)
                usd_value = amount * ticker["last"]
                # usd_value = amount * price

            portfolio_value += usd_value
            asset_breakdown[asset] = round(usd_value, 2)
            asset_amount[asset] = amount

        ###For the total unrealized P/L and the cost basis
        trades = await exchange.fetch_my_trades()
        for trade in trades:
            if trade["side"] == "buy":
                cost = trade["cost"]
                if cost:
                    total_cost_basis += cost
        unrealised_pl = portfolio_value - total_cost_basis
        return {
            "total_portfolio_value": round(portfolio_value, 2),
            "total_asset_breakdown": asset_breakdown,
            "total_unrealized_p/l": round(unrealised_pl, 2),
            "total_cost_basis": round(total_cost_basis, 2),
            "total_asset_amount": asset_amount,
        }

    finally:
        if exchange:
            await exchange.close()
