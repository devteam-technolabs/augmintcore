from coingecko_sdk import AsyncCoingecko
from datetime import datetime
from app.core.config import get_settings

settings = get_settings()

COINGECKO_PRO_API_KEY = settings.COINGECKO_PRO_API_KEY

cg = AsyncCoingecko(
    pro_api_key=COINGECKO_PRO_API_KEY,
    environment="pro"
)
TIMEFRAME_MAP = {
    "1h": 1,
    "24h": 1,
    "7d": 7,
    "1m": 30,
    "1y": 365,
    "all": "max"
}
PRO_DAILY_DAYS = {1, 7, 14, 30, 90, 180}
PRO_HOURLY_DAYS = {1, 7, 14, 30, 90}

async def get_coin_data(coin_ids):
    response =await cg.coins.markets.get(
        vs_currency="usd",
        ids=coin_ids,
        order="market_cap_desc",
        per_page=10,
        page=1,
        sparkline=False
    )
    result =[]
    for coin in response:
        final_value = f"{coin.total_volume/coin.market_cap:.2%}"
        clean_string = final_value.replace('%', '')
        result.append({
            "id": coin.id,
            "symbol": coin.symbol,
            "price": coin.current_price,
            "volume_24h": coin.total_volume,
            "vol/market_cap_24h": float(clean_string),
            "fdv": coin.fully_diluted_valuation,
        })

    
    return result


async def get_data_chart(coin_id:str,timeframe: str):
    days = TIMEFRAME_MAP.get(timeframe, 1)
    data = await cg.coins.market_chart.get(
        id = coin_id,
        vs_currency="usd",
        days=days
    )
    result = []
    print("data",data)
    result.append( {
        "prices": data.prices,
        "market_caps": data.market_caps,
        "volumes": data.total_volumes
    })
    return result


# async def get_ohlc(coin_id:str,days:str,interval:str|None):
#     if interval == "daily":
#         if days not in PRO_DAILY_DAYS:
#             raise ValueError("Invalid days for daily interval")
#     elif interval == "hourly":
#         if days not in PRO_HOURLY_DAYS:
#             raise ValueError("Invalid days for hourly interval")
#     data = await cg.coins.ohlc.get(
#         id =coin_id,
#         vs_currency="usd",
#         days=days,
#         interval=interval
#     )
#     result =[]
#     for candle in data:
#         result.append({
#             "time": int(candle[0]),
#                 "open": candle[1],
#                 "high": candle[2],
#                 "low": candle[3],
#                 "close": candle[4],

#         })
#     return result

