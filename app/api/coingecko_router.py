from fastapi import APIRouter,Query,HTTPException, Security, Depends
from typing import List,Optional
from app.schemas.user import(CoinGeckoCoinDataResponse)
from app.coingecko.historical_data_func import get_coin_data,get_data_chart
from app.models.user import User, UserExchange
from app.auth.user import auth_user
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_session
from app.coinbase.exchange import get_volatility_data



router = APIRouter(prefix="/coingecko", tags=["CoinGecko"])

@router.get("/market-data",response_model= CoinGeckoCoinDataResponse)
async def get_market_data(coin_ids: Optional[List[str]] = Query(None),
     current_user: User = Security(auth_user.get_current_user),
                           db: AsyncSession = Depends(get_async_session)):
    
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if not coin_ids:
        raise HTTPException(status_code=404, detail="Coin_id not found")
    result = await get_coin_data(coin_ids=coin_ids)
    print("coinnnnnn---",coin_ids)
    volatility_data = await get_volatility_data(symbol=coin_ids[0], user=user, db=db)
    return {
        "status_code":200,
        "message":"Successfully get the Coin Data",
        "result":result,
        "volatility_data": volatility_data
    }


@router.get("/market-chart-data",response_model= CoinGeckoCoinDataResponse)
async def get_market_chart(timeframe:str, 
                           coin_id: str = Query(..., description="CoinGecko coin id, e.g. bitcoin")  ):
    
    if not timeframe and coin_id:
        raise HTTPException(status_code=404, detail="Coin_id not found")
    print("coinnnnnn---",coin_id)
    result= await get_data_chart(coin_id=coin_id,timeframe=timeframe)
    return {
        "status_code":200,
        "message":"Successfully get the Coin chart",
        "result":result
    }

# @router.get("/ohlc",response_model=CoinGeckoCoinDataResponse)
# async def get_ohlc_data(days,interval:str|None,coin_id :str = Query(..., description="CoinGecko coin id, e.g. bitcoin")):
#     result = await get_ohlc(coin_id=coin_id,days=days,interval=interval)
#     return {
#         "status_code":200,
#         "message":"Successfully get the Coin chart",
#         "result":result,
#         "counts":len(result)
#     }
