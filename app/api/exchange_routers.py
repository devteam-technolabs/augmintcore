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

from app.coinbase.exchange import validate_coinbase_api

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

    # 2. Check duplicate
    exists = await db.execute(
        select(UserExchange).where(
            UserExchange.user_id == user.id,
            UserExchange.exchange_name == data.exchange_name.lower(),
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(400, f"{data.exchange_name} already connected")

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
        api_key=data.api_key,
        api_secret=data.api_secret,
        passphrase=data.passphrase,
    )

    db.add(user_exchange)

    # 5. Mark user as connected
    user.is_exchange_connected = True

    await db.commit()
    await db.refresh(user)
    await db.refresh(user_exchange)

    # 6. Generate tokens
    access = create_access_token({"user_id": user.id})
    refresh = create_refresh_token({"user_id": user.id})

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
