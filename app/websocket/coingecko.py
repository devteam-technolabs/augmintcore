import httpx
from app.core.config import get_settings

settings = get_settings()


async def fetch_top_ten(vs_currency: str | None = None):
    url = settings.COINGECKO_MARKETS_URL
    vs_currency = vs_currency or settings.DEFAULT_VS_CURRENCY

    params = {
        "vs_currency": vs_currency.lower(),
        "order": "market_cap_desc",
        "per_page": 10,
        "page": 1,
        "sparkline": True,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url, params=params)
        res.raise_for_status()

    data = res.json()

    return [
        {
            "id": coin["id"],
            "symbol": coin["symbol"].upper(),
            "name": f"{coin['symbol'].upper()}/{vs_currency.upper()}",
            "icon": coin["image"],
            "price": coin["current_price"],
            "change": coin["price_change_percentage_24h"],
            "sparkline": coin["sparkline_in_7d"]["price"],
            "product_id": f"{coin['symbol'].upper()}-{vs_currency.upper()}",
        }
        for coin in data
    ]
