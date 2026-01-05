from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import ccxt.async_support as ccxt
from app.db.session import get_async_session
from app.auth.user import auth_user
from app.schemas.exchange import ExchangeConnectRequest, ExchangeConnectResponse, CCTXResponse
from app.schemas.user import UserResponse
from app.models.user import User, UserExchange
from app.services.auth_service import create_access_token, create_refresh_token
from app.security.kms_service import kms_service
from app.coinbase.exchange import validate_coinbase_api,get_crypt_currencies,user_portfolio_data,get_total_coin_value,get_total_account_value,get_profit_and_loss

router = APIRouter(prefix="/exchange", tags=["Exchange"])


@router.post("/coinbase/connect", response_model=ExchangeConnectResponse)
async def connect_exchange(
    data: ExchangeConnectRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user),
):

    # 1. Check user
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    access = create_access_token({"user_id": user.id})
    refresh = create_refresh_token({"user_id": user.id})

    # 2. Check duplicate
    exists = await db.execute(
        select(UserExchange).where(
            UserExchange.user_id == user.id,
            UserExchange.exchange_name == data.exchange_name.lower(),
        )
    )
    if exists.scalar_one_or_none():
        return {
            "message": "{exchange_name} already connected",
            "user": user,
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "status_code": 200
        }
        

    # 3. Validate Coinbase credentials using CCXT
    is_valid = await validate_coinbase_api(
        api_key=data.api_key,
        api_secret=data.api_secret,
        passphrase=data.passphrase
    )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API credentials — Coinbase connection failed"
        )

    # 4. Save exchange credentials
    user_exchange = UserExchange(
            user_id=user.id,
            exchange_name=data.exchange_name.lower(),
            api_key=await kms_service.encrypt(data.api_key),
            api_secret=await kms_service.encrypt(data.api_secret),
            passphrase=await kms_service.encrypt(data.passphrase),
        )


    db.add(user_exchange)

    # 5. Mark user as connected
    user.is_exchange_connected = True
    user.step = 3

    await db.commit()
    await db.refresh(user)
    await db.refresh(user_exchange)

    # 6. Generate tokens
    

    return {
        "message": "Coinbase exchange connected successfully",
        "user": user,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "status_code": 200
    }


@router.get("/cctx", response_model=CCTXResponse)
async def connect_exchange(
):    # Just a test endpoint to list all exchanges in CCXT
    exchnges_data = ccxt.exchanges
    return {
        "message": "List all exchanges in CCXT",
        "status_code": 200,
        "data": exchnges_data,
    }


@router.get("/crypto/currenices",response_model=CCTXResponse)
async def get_crypt_prices(exchange_name :str, db: AsyncSession = Depends(get_async_session),
    current_user: User = Security(auth_user.get_current_user)):

    results = await db.execute(select(User).where(User.id==current_user.id))
    user = results.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")
    
    try:

        crypto_values_data = await get_crypt_currencies(exchange_name,user,db)
        return {
            "message":"List of all crypto currencies",
            "status_code": 200,
            "data": crypto_values_data

        }
    except Exception as e:
        return {
            "message": "An error occured",
            "status_code": 400,
            "data":str(e)
        }


@router.get("/get-clean-portfolio")
async def get_portfolio(exchange_name:str, db:AsyncSession=Depends(get_async_session),
        current_user:User=Security(auth_user.get_current_user)):
        results = await db.execute(select(User).where(User.id ==current_user.id))
        user = results.scalar_one_or_none()

        if not user:
            raise HTTPException(404,"User not found")

        try:
            get_user_portfolio_data = await user_portfolio_data(exchange_name,user,db)

            return {
                "message": "List of all data ",
                "status_code" :200,
                "data": get_user_portfolio_data
            }
        except Exception as e:
             return {
            "message": "An error occured",
            "status_code": 400,
            "data":str(e)
        }

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





@router.get("/portfolio/profit-loss")
async def portfolio_profit_loss(
    exchange_name: str,
    current_user: User = Security(auth_user.get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await get_profit_and_loss(
        exchange_name=exchange_name.lower(),
        user=current_user,
        db=db
    )
