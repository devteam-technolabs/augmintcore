import ccxt.async_support as ccxt
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.user import auth_user
from app.coinbase.exchange import (
    buy_sell_order_execution,
    calculate_dashboard,
    fetch_all_orders,
    fetch_close_orders,
    fetch_open_orders,
    get_crypt_currencies,
    get_historical_data,
    get_historical_ohlc_data,
    get_profit_and_loss,
    get_total_account_value,
    get_total_coin_value,
    user_portfolio_data,
    validate_coinbase_api,
)
from app.db.session import get_async_session
from app.models.user import User, UserExchange
from app.schemas.buy_sell import BuySellOrderRequest
from app.schemas.exchange import (
    CCTXResponse,
    ExchangeConnectRequest,
    ExchangeConnectResponse,
)
from app.schemas.user import UserResponse
from app.security.kms_service import kms_service
from app.services.auth_service import create_access_token, create_refresh_token
from app.services.secret_manager_service import secrets_manager_service
from app.utils.exchange_utils import get_exchange_by_str
from app.coinbase.exchange import get_keys
from app.coinbase.coinbase_cctx import get_working_coinbase_exchange
from app.models.user import PortfolioSnapshot
from fastapi_utilities import repeat_every

router = APIRouter(prefix="/exchange", tags=["Exchange"])


@router.post("/coinbase/connect", response_model=ExchangeConnectResponse)
async def connect_exchange(
    data: ExchangeConnectRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):
    # 1. Check user
    print("DATA ===>", data)
    print("1")
    result = await db.execute(select(User).where(User.id == current_user.id))
    print("2")
    user = result.scalar_one_or_none()
    print("3")
    if not user:
        raise HTTPException(404, "User not found")
    print("4")
    access = create_access_token({"user_id": user.id})
    print("5")
    refresh = create_refresh_token({"user_id": user.id})

    exchange = get_exchange_by_str(data.exchange_name.lower())

    if not exchange:
        raise HTTPException(status_code=400, detail="Unsupported exchange")

    exchange_name = exchange["exchange_str"]

    # 2. Check duplicate
    print("6")
    exists = await db.execute(
        select(UserExchange).where(
            UserExchange.user_id == user.id,
            UserExchange.exchange_name == exchange_name,
        )
    )
    print("7")
    if exists.scalar_one_or_none():
        print("8")
        return {
            "message": f"{data.exchange_name} already connected",
            "user": user,
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "status_code": 200,
        }

    # 3. Validate Coinbase credentials using CCXT
    print("9")
    is_valid = await validate_coinbase_api(
        api_key=data.api_key, api_secret=data.api_secret, passphrase=data.passphrase
    )
    print("10")
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API credentials — Coinbase connection failed",
        )

    print("11")
    # 4. Store credentials in AWS Secrets Manager
    try:
        secret_arn = await secrets_manager_service.store_exchange_credentials(
            user_id=user.id,
            exchange_name=exchange_name,
            api_key=data.api_key,
            api_secret=data.api_secret,
            passphrase=data.passphrase,
        )
        print(f"Stored credentials in Secrets Manager: {secret_arn}")
    except Exception as e:
        print(f"Failed to store in Secrets Manager: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to securely store credentials"
        )

    # 5. Save exchange record with encrypted values (dual storage approach)
    # Store encrypted values in DB as backup/reference
    user_exchange = UserExchange(
        user_id=user.id,
        exchange_name=exchange_name,
        api_key=await kms_service.encrypt(data.api_key),
        api_secret=await kms_service.encrypt(data.api_secret),
        passphrase=await kms_service.encrypt(data.passphrase),
        secret_arn=secret_arn,
    )

    print("12")
    db.add(user_exchange)
    print("13")

    # 6. Mark user as connected
    user.is_exchange_connected = True
    user.step = 3
    print("14")

    await db.commit()
    await db.refresh(user)
    await db.refresh(user_exchange)

    return {
        "message": f"{data.exchange_name} connected successfully",
        "user": user,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "status_code": 200,
    }


@router.get("/cctx", response_model=CCTXResponse)
async def connect_exchange():  # Just a test endpoint to list all exchanges in CCXT
    exchnges_data = ccxt.exchanges
    return {
        "message": "List all exchanges in CCXT",
        "status_code": 200,
        "data": exchnges_data,
    }


@router.get("/crypto/currenices", response_model=CCTXResponse)
async def get_crypt_prices(
    exchange_name: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):

    results = await db.execute(select(User).where(User.id == current_user.id))
    user = results.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    try:

        crypto_values_data = await get_crypt_currencies(exchange_name, user, db)
        return {
            "message": "List of all crypto currencies",
            "status_code": 200,
            "data": crypto_values_data,
        }
    except Exception as e:
        return {"message": "An error occured", "status_code": 400, "data": str(e)}


@router.get("/get-clean-portfolio")
async def get_portfolio(
    exchange_name: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):
    results = await db.execute(select(User).where(User.id == current_user.id))
    user = results.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    try:
        get_user_portfolio_data = await user_portfolio_data(exchange_name, user, db)

        return {
            "message": "List of all data ",
            "status_code": 200,
            "data": get_user_portfolio_data,
        }
    except Exception as e:
        return {"message": "An error occured", "status_code": 400, "data": str(e)}


@router.get("/total-coin-value")
async def total_coin_value(
    exchange_name: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):
    # 1️⃣ Validate user
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2️⃣ Get total value
    try:
        print("Fetching total coin value...")
        data = await get_total_coin_value(exchange_name, user, db)

        return {
            "message": "Total coin value fetched successfully",
            "status_code": 200,
            "data": data,
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch total coin value: {str(e)}",
        )


@router.get("/portfolio/total-account-value")
async def total_account_value(
    exchange_name: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = await get_total_account_value(exchange_name.lower(), user, db)

    return {
        "message": "Total account value fetched successfully",
        "status_code": 200,
        "data": data,
    }


@router.get("/portfolio/all/orders")
async def total_account_value(
    exchange_name: str,
    symbol: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = await fetch_all_orders(exchange_name.lower(), symbol, user, db)

    return {
        "message": "Orders fetched successfully",
        "status_code": 200,
        "data": data,
    }


@router.get("/portfolio/close/orders")
async def total_account_value(
    exchange_name: str,
    symbol: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = await fetch_close_orders(exchange_name.lower(), symbol, user, db)

    return {
        "message": "Orders fetched successfully",
        "status_code": 200,
        "data": data,
    }


@router.get("/portfolio/open/orders")
async def total_account_value(
    exchange_name: str,
    symbol: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = await fetch_open_orders(
        exchange_name.lower(),
        symbol,
        user,
        db,
    )

    return {
        "message": "Orders fetched successfully",
        "status_code": 200,
        "data": data,
    }


@router.post("/buy-sell-order")
async def buy_sell_order(
    payload: BuySellOrderRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        data = await buy_sell_order_execution(
            exchange_name=payload.exchange_name,
            symbol=payload.symbol,
            side=payload.side,
            order_type=payload.order_type,
            quantity=payload.quantity,  # Was amount -> now quantity used as amount for order creation
            total_cost=payload.total_cost,
            limit_price=payload.limit_price,
            user=user,
            db=db,
        )

        return {
            "message": "Order executed successfully",
            "status_code": 200,
            "data": data,
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/portfolio/profit-loss")
async def portfolio_profit_loss(
    exchange_name: str,
    current_user: User = Security(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await get_profit_and_loss(
        exchange_name=exchange_name.lower(), user=current_user, db=db
    )


# this endpoint is an old endpoint which provide historical data but it is a slow api.
@router.get("/get-historical-data")
async def get_ohlc_data(
    timeframe,
    period,
    coin_id,
    current_user: User = Security(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await get_historical_data(
        timeframe=timeframe, period=period, user=current_user, db=db, symbol=coin_id
    )


# New api for historical ohlc data which is faster than the old one and provide data in ohlc format with pagination support.
@router.get("/ohlc")
async def get_ohlc_data(
    coin_id: str,
    timeframe: str,
    before: int | None = None,
    current_user: User = Security(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await get_historical_ohlc_data(
        user=current_user,
        timeframe=timeframe,
        symbol=coin_id,
        before=before,
        db=db,
    )


@router.get("/get_profit_loss")
async def dashboard_data(
    exchange_name: str,
    current_user: User = Security(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await calculate_dashboard(
        exchange_name=exchange_name, user=current_user, db=db
    )

from app.db.session import AsyncSessionLocal
@router.on_event("startup")
@repeat_every(seconds=86400,wait_first=False) 
async def populate_protfolio_value(
):  
    print("RUNNING PORTFOLIO SNAPSHOT TASK")
    async with AsyncSessionLocal() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()

        print("TOTAL USERS:", len(users))
        for user in users:
            exchange = None
            keys = await get_keys(exchange_name="coinbase",user_id=user.id,db=db)
            print(keys)
            if not keys:
                print(f"No exchange keys for user {user.id}")
                continue

            try:
                exchange = await get_working_coinbase_exchange(
                    keys["api_key"], keys["api_secret"], keys.get("passphrase", "")
                )
                balance = (
                    exchange._cached_validation_balance
                    if hasattr(exchange, "_cached_validation_balance")
                    else await exchange.fetch_balance()
                )
                print(balance)
                total_assets_balance = balance["total"]
                print(total_assets_balance)
                STABLE_COINS = {"USDC", "USDT"}
                # tickers = await exchange.fetch_ticker()
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
                        # usd_value = amount * price

                    portfolio_value += usd_value
                snapshot = PortfolioSnapshot(
                        user_id=user.id,
                        portfolio_value=portfolio_value
                    )

                db.add(snapshot)
                await db.commit()
            except Exception as e:
                print(f"Error processing user {user.id}: {e}")

            finally:
                if exchange:
                    await exchange.close()

    
