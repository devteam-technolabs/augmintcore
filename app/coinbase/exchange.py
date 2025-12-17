import ccxt.async_support as ccxt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_async_session
from app.security.kms_service import  kms_service
from app.models.user import User, UserExchange
from fastapi import Depends

def clean_private_key(pem: str) -> str:
    return pem.replace("\\n", "\n").strip()


async def validate_coinbase_api(api_key: str, api_secret: str, passphrase: str) -> bool:
    private_key = clean_private_key(api_secret)
    print("Validating Coinbase API credentials...", api_key, private_key)

    try:
        exchange = ccxt.coinbase({
            "apiKey": api_key,
            "secret": private_key,
            "enableRateLimit": True,
        })
        exchange.has["fetchCurrencies"] = False
        # If authentication fails, this call will raise an exception
        accounts = await exchange.v3PrivateGetBrokerageAccounts()
        print("Accounts:", accounts)
        if "accounts" not in accounts:
            return False  # Auth FAILED 

        return True   # Auth SUCCESS

    except Exception:
        return False  # Auth FAILED

    finally:
        await exchange.close()

async def get_keys(exchange_name:str,user_id:int, db: AsyncSession = Depends(get_async_session),):

    exchange_name = exchange_name.lower()

    result = await db.execute(
        select(UserExchange).where(
            UserExchange.user_id == user_id,
            UserExchange.exchange_name == exchange_name
        )
    )
    ex = result.scalar_one_or_none()

    if not ex:
        raise HTTPException(404, "No API keys found for this exchange")

    return {
        "exchange": exchange_name,
        "api_key": await kms_service.decrypt(ex.api_key),
        "api_secret": await kms_service.decrypt(ex.api_secret),
        "passphrase": await kms_service.decrypt(ex.passphrase) if ex.passphrase else None,
        "created_at": ex.created_at
    }
async def get_crypt_currencies(exchange_name, user, db):
    exchange = None
    try:
        user_keys = await get_keys(exchange_name, user.id, db)
        usr_api_key = user_keys['api_key']
        usr_secret_key = user_keys['api_secret']

        exchange = ccxt.coinbase({
            "apiKey": usr_api_key,
            "secret": usr_secret_key,
            "enableRateLimit": True,
        })

        # IMPORTANT: required by ccxt async
        await exchange.load_markets()

        accounts = await exchange.v3PrivateGetBrokerageAccounts()

        if "accounts" in accounts:
            tickers = await exchange.fetch_tickers()
            prices = {
                symbol: data.get("last")
                for symbol, data in tickers.items()
                if data.get("last") is not None
            }
            return prices

        return False

    except Exception as e:
        return {f"Errors{e}"}

    finally:
        if exchange:
            await exchange.close()

async def user_portfolio_data(exchange_name,user,db):
    usr_keys = await get_keys(exchange_name,user.id,db)
    user_api_key = usr_keys['api_key']
    user_secret_key = usr_keys['api_secret']
    

    exchange = ccxt.coinbaseadvanced({
                "apiKey": user_api_key,
                "secret": user_secret_key,
                "enableRateLimit": True,
                "options": {
                    "brokerage": True,
                    "fetchMarkets": False,
                }
    })

    try:
        # 1️⃣ Fetch balances
        balance = await exchange.fetch_balance()

        assets = []
        total_usd_value = 0.0

        # 2️⃣ Load tickers once
        tickers = await exchange.fetch_tickers()

        for symbol, data in balance.items():
            if symbol == "info":
                continue

            total = data.get("total", 0)
            if not total or total <= 0:
                continue

            asset_data = {
                "asset": symbol,
                "free": float(data.get("free", 0)),
                "locked": float(data.get("used", 0)),
                "total": float(total),
                "usd_price": None,
                "usd_value": None,
            }

            # 3️⃣ USD valuation
            if symbol == "USD":
                asset_data["usd_price"] = 1
                asset_data["usd_value"] = asset_data["total"]
            else:
                pair = f"{symbol}/USD"
                ticker = tickers.get(pair)

                if ticker and ticker.get("last"):
                    price = float(ticker["last"])
                    asset_data["usd_price"] = price
                    asset_data["usd_value"] = price * asset_data["total"]

            if asset_data["usd_value"]:
                total_usd_value += asset_data["usd_value"]

            assets.append(asset_data)
            print(assets)

        return {
            "total_assets_value_usd": round(total_usd_value, 2),
            "total_currencies": len(assets),
            "assets": assets
        }

    finally:
        await exchange.close()






