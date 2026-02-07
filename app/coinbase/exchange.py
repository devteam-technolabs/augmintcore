# -----------------------------------------
# Standard Library Imports
# -----------------------------------------
import asyncio
import functools
import math
from datetime import datetime, timedelta

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
from app.coinbase.coinbase_cctx import get_working_coinbase_exchange
from app.auth.user import auth_user

# -----------------------------------------
# Local Application Imports
# -----------------------------------------
from app.db.session import get_async_session
from app.models.user import User, UserExchange
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
    "polygon": "MATIC/USD",
}


def clean_private_key(pem: str) -> str:
    return pem.replace("\\n", "\n").strip()





async def validate_coinbase_api(api_key: str, api_secret: str, passphrase: str) -> bool:
    exchange = None
    private_key = clean_private_key(api_secret)

    try:
        print("Trying Coinbase Advanced connection")
        exchange = ccxt.coinbaseadvanced({
            "apiKey": api_key,
            "secret": private_key,     # raw secret
            "enableRateLimit": True,
        })
        exchange.options['adjustForTimeDifference'] = True  
       
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
    print(result, "gggggggggggggggggggggggggggg")
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
        print("keys", keys)

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

        exchange.options['adjustForTimeDifference'] = True  

        
        if hasattr(exchange, '_cached_validation_balance'):
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


async def buy_sell_order_execution(
    symbol: str,
    side: str,                
    amount: float,             
    order_type: str,           
    user,
    db,
    exchange_name: str,
    price: float | None = None ,
    exchange = None):

    try:
        keys = await get_keys(exchange_name, user.id, db)

        api_key = keys["api_key"]
        api_secret = keys["api_secret"]
        passphrase = keys.get("passphrase")

        # Validate keys first
        val_exchange = await get_working_coinbase_exchange(
            api_key,
            api_secret,
            passphrase,
        )

        if not val_exchange:
            raise RuntimeError("No valid Coinbase exchange found")

        # Capture ID and close validation connection
        exchange_id = val_exchange.id
        await val_exchange.close()

        # Instantiate fresh exchange strictly for execution
        if exchange_id == "coinbaseadvanced":
            exchange = ccxt.coinbaseadvanced({
                "apiKey": api_key,
                "secret": clean_private_key(api_secret),
                "enableRateLimit": True,
            })
            exchange.options["adjustForTimeDifference"] = True
        else:
            exchange = ccxt.coinbaseexchange({
                "apiKey": api_key,
                "secret": api_secret,
                "password": passphrase,
                "enableRateLimit": True,
            })
            exchange.set_sandbox_mode(True)
       

        # --- Safety checks ---
        side = side.lower()
        order_type = order_type.lower()

        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")

        if order_type not in ("market", "limit"):
            raise ValueError("order_type must be 'market' or 'limit'")

        if order_type == "limit" and price is None:
            raise ValueError("price is required for limit orders")

        # --- Load markets (important for precision) ---
        await exchange.load_markets()

        # 1. Fetch Ticker (Public) and Prepare Params
        # We do this first to calculate quote_size if needed
        req_params = {}
        # Coinbase Advanced Trade requires product_id sometimes
        try:
            market = exchange.market(symbol)
            product_id = market['id']  # e.g. "BTC-USD" 
            req_params["product_id"] = product_id
        except:
             # Fallback if market not found (shouldn't happen after load_markets)
             pass

        if order_type == "market" and side == "buy":
             # Fix: "unknown field base_size" -> Use 'quote_size' for Market Buys
             ticker = await exchange.fetch_ticker(symbol)
             current_price = ticker['last']
             estimated_cost = float(amount) * float(current_price)
             
             # round to 2 decimals for USD
             # req_params["quote_size"] = f"{estimated_cost:.2f}" # Rejected by API
             
             # We will pass 'estimated_cost' as the amount to create_order
             # which CCXT usually maps to the correct quote field for market buys.
        elif order_type == "market" and side == "sell":
             # Market Sells use base_size
             req_params["base_size"] = str(amount)

        # 2. Safety Delay & Private Call 1 (Fetch Accounts)
        await asyncio.sleep(1.0)
        
        # Populate internal account cache (Critical for "account not available" fix)
        # Wrap in retry to avoid noisy 401s
        for i in range(2):
            try:
                await exchange.fetch_accounts()
                break
            except (ccxt.AuthenticationError, ccxt.ExchangeError) as e:
                # print(f"⚠️ Fetch accounts attempt {i+1} failed: {e}")
                if i == 0:
                    await asyncio.sleep(1.0)
                    continue
                # If it fails twice, we log but carry on, as it might not be strictly blocked if user provided IDs
                print(f"⚠️ Failed to pre-fetch accounts after retries: {e}")

        # 3. Safety Delay & Private Call 2 (Create Order)
        # Sleep AGAIN to ensure 'fetch_accounts' nonce doesn't collide with 'create_order' nonce
        await asyncio.sleep(1.0)

        # Retry wrapper for execution
        for i in range(2):
            try:
                if order_type == "market":
                    exchange.options["createMarketBuyOrderRequiresPrice"] = False
                    
                    # Based on user's working example:
                    # order = await exchange.create_order(
                    #     symbol="LTC/USDC", type="market", side="buy",
                    #     amount=1, params={"cost": 1.6}
                    # )
                    
                    if side == "buy":
                        # For Market Buy, we must send "cost" (quote amount)
                        # We calculated 'estimated_cost' above.
                        # CCXT usually maps the main 'amount' argument to base_size.
                        # But for Coinbase Advanced Market Buy, we want to specify cost.
                        
                        # Use generic create_order to have full control
                        order = await exchange.create_order(
                            symbol=symbol,
                            type="market",
                            side="buy",
                            amount=estimated_cost, # CCXT often uses this as cost if 'market' buy
                            params=req_params # Contains 'product_id'
                        )
                    else:
                        # For Market Sell, we send base_size (which is the main 'amount')
                        order = await exchange.create_market_order(
                            symbol=symbol,
                            side=side,
                            amount=amount, 
                            params=req_params
                        )
                else:
                    order = await exchange.create_limit_order(
                        symbol=symbol,
                        side=side,
                        amount=amount,
                        price=price,
                    )
                
                # If successful, break
                break
            
            # FAIL FAST errors (Don't retry)
            except (ccxt.InsufficientFunds, ccxt.InvalidOrder, ccxt.OrderNotFound, ccxt.BadSymbol) as e:
                raise e

            # RETRYABLE errors
            except (ccxt.AuthenticationError, ccxt.ExchangeError, ccxt.NetworkError) as e:
                if i == 0:
                    print(f"⚠️ Order attempt 1 failed ({e}). Retrying in 1s...")
                    await asyncio.sleep(1.0)
                    continue
                raise e

        return {
            "status": "success",
            "order_id": order.get("id"),
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
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
            if currency == "USD":
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

            pair = f"{currency}/USD"
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
