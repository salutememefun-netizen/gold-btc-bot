import os
import logging
import requests

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Live price fetcher – Yahoo → Yahoo quote → Coingecko / Alpha Vantage
# ----------------------------------------------------------------------
def get_live_price(asset: str):
    """
    Return (price, source_symbol) for the requested asset.
    asset: 'gold' or 'btc'
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
        )
    })

    # 1️⃣  Yahoo chart API (original logic)
    for symbol in SYMBOLS.get(asset, []):
        try:
            r = session.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={
                    "interval": "1m",
                    "range": "1d",
                    "includePrePost": "true",
                },
                timeout=15,
            )
            if r.status_code != 200:
                logger.debug(f"Yahoo chart {symbol} returned {r.status_code}")
                continue

            data = r.json()
            result = data.get("chart", {}).get("result")
            if not result:
                logger.debug(f"No chart result for {symbol}")
                continue

            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            if price is None:
                # fall back to the last close value
                quotes = result[0].get("indicators", {}).get("quote", [])
                closes = quotes[0].get("close", []) if quotes else []
                for v in reversed(closes):
                    if v is not None:
                        price = v
                        break

            if price is not None:
                return float(price), symbol
        except Exception as exc:
            logger.warning(f"Yahoo chart error for {symbol}: {exc}")

    # 2️⃣  Yahoo quote endpoint – often returns a single price
    for symbol in SYMBOLS.get(asset, []):
        try:
            r = session.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": symbol},
                timeout=10,
            )
            if r.status_code != 200:
                logger.debug(f"Yahoo quote {symbol} returned {r.status_code}")
                continue

            data = r.json()
            result = data.get("quoteResponse", {}).get("result", [])
            if not result:
                logger.debug(f"No quote result for {symbol}")
                continue

            quote = result[0]
            price = quote.get("regularMarketPrice")
            if price is not None:
                return float(price), symbol
        except Exception as exc:
            logger.warning(f"Yahoo quote error for {symbol}: {exc}")

    # 3️⃣  Coingecko for BTC (free, no API key)
    if asset == "btc":
        try:
            r = session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                price = data.get("bitcoin", {}).get("usd")
                if price is not None:
                    return float(price), "Coingecko"
        except Exception as exc:
            logger.warning(f"Coingecko error: {exc}")

    # 4️⃣  Alpha Vantage for GOLD (demo key – replace with your own if you have one)
    if asset == "gold":
        try:
            api_key = os.getenv("ALPHA_VANTAGE_KEY", "demo")  # 'demo' works for up to 5 calls/min
            r = session.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": "GC=F",
                    "apikey": api_key,
                },
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                quote = data.get("Global Quote", {})
                price_str = quote.get("05. price")
                if price_str:
                    return float(price_str), "AlphaVantage"
        except Exception as exc:
            logger.warning(f"Alpha Vantage error: {exc}")

    # If all attempts fail
    logger.warning(f"Could not fetch price for {asset}")
    return None, None
