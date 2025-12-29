# app/services/candles.py
import httpx
from app.core.config import get_settings

settings = get_settings()


async def fetch_candles(symbol: str, granularity: int = 3600):
    product_id = f"{symbol.upper()}-USD"

    url = (
        settings.COINBASE_REST_URL
        + settings.COINBASE_CANDLES_PATH.format(product_id=product_id)
    )

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url, params={"granularity": granularity})
        res.raise_for_status()

    candles = res.json()

    if not candles:
        return None

    # Coinbase returns newest candle FIRST
    latest = candles[0]

    return {
        "symbol": product_id,
        "granularity": granularity,
        "time": latest[0],
        "low": latest[1],
        "high": latest[2],
        "open": latest[3],
        "close": latest[4],
        "volume": latest[5],
    }



# # app/services/candles.py
# import httpx
# from app.core.config import get_settings

# settings = get_settings()


# async def fetch_candles(symbol: str, granularity: int = 3600):
#     product_id = f"{symbol.upper()}-USD"

#     url = (
#         settings.COINBASE_REST_URL
#         + settings.COINBASE_CANDLES_PATH.format(product_id=product_id)
#     )

#     async with httpx.AsyncClient(timeout=10) as client:
#         res = await client.get(url, params={"granularity": granularity})
#         res.raise_for_status()

#     candles = res.json()

#     return {
#         "symbol": product_id,
#         "granularity": granularity,
#         "data": [
#             {
#                 "time": c[0],
#                 "low": c[1],
#                 "high": c[2],
#                 "open": c[3],
#                 "close": c[4],
#                 "volume": c[5],
#             }
#             for c in candles
#         ]
#     }
