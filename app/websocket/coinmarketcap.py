import httpx
import logging
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

CMC_DETAIL_URL = settings.CMC_DETAIL_URL
CMC_LISTING_URL = settings.CMC_LISTING_URL

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://coinmarketcap.com/"
}

async def fetch_cmc_details(symbol: str):
    """
    Fetches accurate real-time market data from CoinMarketCap's public data API.
    """
    symbol_to_slug = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
        "ADA": "cardano", "DOGE": "dogecoin", "DOT": "polkadot", "MATIC": "polygon",
        "BNB": "binancecoin", "USDT": "tether", "USDC": "usd-coin", "LINK": "chainlink",
        "AVAX": "avalanche-2", "TRX": "tron", "TON": "the-open-network",
    }
    
    slug = symbol_to_slug.get(symbol.upper(), symbol.lower())
    params = {"slug": slug, "range": "1D"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(CMC_DETAIL_URL, params=params, headers=HEADERS)
            res.raise_for_status()
            data = res.json()
            if not data or "data" not in data: return None
            
            coin_data = data["data"]
            stats = coin_data.get("statistics", {})
            return {
                "symbol": coin_data.get("symbol"),
                "name": coin_data.get("name"),
                "price": stats.get("price"),
                "volume_24h": stats.get("volume24h"),
                "market_cap": stats.get("marketCap"),
                "fdv": stats.get("fullyDilutedMarketCap"),
                "vol_mkt_cap_ratio": stats.get("turnover"),
                "price_change_24h": stats.get("priceChangePercentage24h"),
                "high_24h": stats.get("high24h"),
                "low_24h": stats.get("low24h"),
                "circulating_supply": stats.get("circulatingSupply"),
                "total_supply": stats.get("totalSupply"),
                "max_supply": stats.get("maxSupply"),
            }
    except Exception as e:
        logger.error(f"Error fetching CMC details for {symbol}: {e}")
        return None

async def fetch_top_ten_cmc():
    """
    Fetches the top 10 coins from CoinMarketCap with accurate listing data.
    """
    params = {
        "start": 1,
        "limit": 10,
        "sortBy": "market_cap",
        "sortType": "desc",
        "convert": "USD"
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(CMC_LISTING_URL, params=params, headers=HEADERS)
            res.raise_for_status()
            data = res.json()
            if not data or "data" not in data: return []
            
            coins = data["data"].get("cryptoCurrencyList", [])
            result = []
            for coin in coins:
                quote = coin["quotes"][0] # USD quote
                result.append({
                    "id": coin["id"],
                    "symbol": coin["symbol"],
                    "name": f"{coin['symbol']}/USD",
                    "price": quote["price"],
                    "change": quote["percentChange24h"],
                    "product_id": f"{coin['symbol']}-USD",
                })
            return result
    except Exception as e:
        logger.error(f"Error fetching CMC top ten: {e}")
        return []
