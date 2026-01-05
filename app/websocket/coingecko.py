import httpx
from app.core.config import get_settings

settings = get_settings()


# Old code
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


# New updated code for new requirement
async def fetch_top_ten_v2(vs_currency: str | None = None):
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
            "product_id": f"{coin['symbol'].upper()}-{vs_currency.upper()}",
            "market_cap": coin.get("market_cap"),
            "total_volume": coin.get("total_volume"),
            "fdv": coin.get("fully_diluted_valuation"),
            "change": coin["price_change_percentage_24h"],
            "sparkline": coin["sparkline_in_7d"]["price"],

        }
        for coin in data
    ]

async def fetch_coin_details(symbol: str, vs_currency: str = "usd"):
    """
    Fetches detailed market data for a specific coin from CoinGecko.
    """
    symbol_to_id = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "MATIC": "polygon",
        "BNB": "binancecoin",
        "USDT": "tether",
        "USDC": "usd-coin",
        "LINK": "chainlink",
        "AVAX": "avalanche-2",
        "TRX": "tron",
        "TON": "the-open-network",
    }
    
    coin_id = symbol_to_id.get(symbol.upper(), symbol.lower())
    
    url = settings.COINGECKO_MARKETS_URL
    params = {
        "vs_currency": vs_currency.lower(),
        "ids": coin_id,
        "sparkline": False,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(url, params=params)
        res.raise_for_status()
        data = res.json()

    if not data:
        return None

    coin = data[0]
    return {
        "symbol": coin["symbol"].upper(),
        "market_cap": coin.get("market_cap"),
        "total_volume": coin.get("total_volume"),
        "fdv": coin.get("fully_diluted_valuation"),
        "vol_mkt_cap_ratio": (
            coin.get("total_volume") / coin.get("market_cap") 
            if coin.get("market_cap") and coin.get("total_volume") 
            else 0
        )
    }

