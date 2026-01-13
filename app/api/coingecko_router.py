from fastapi import APIRouter,Query,HTTPException
from typing import List,Optional
from app.schemas.user import(CoinGeckoCoinDataResponse)
from app.coingecko.historical_data_func import get_coin_data,get_data_chart
router = APIRouter(prefix="/coingecko", tags=["CoinGecko"])

@router.get("/market-data",response_model= CoinGeckoCoinDataResponse)
async def get_market_data(coin_ids: Optional[List[str]] = Query(None)):
    if not coin_ids:
        raise HTTPException(status_code=404, detail="Coin_id not found")
    result = await get_coin_data(coin_ids=coin_ids)
    return {
        "status_code":200,
        "message":"Successfully get the Coin Data",
        "result":result
    }


@router.get("/market-chart-data",response_model= CoinGeckoCoinDataResponse)
async def get_market_chart(timeframe:str, 
                           coin_id: str = Query(..., description="CoinGecko coin id, e.g. bitcoin")):
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
