def get_live_price(asset):
    """
    Return (price, source_symbol). Cuba pelbagai sumber dengan debug.
    Gold: gold-api.com → metals-api → Yahoo → Alpha Vantage
    BTC:  Binance → Coingecko → Yahoo
    """
    if asset == "gold":
        # 1️⃣ gold-api.com
        try:
            logger.info("Trying gold-api.com...")
            r = SESSION.get("https://gold-api.com/price/XAU", timeout=10)
            logger.info(f"gold-api.com response: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                logger.info(f"gold-api.com data: {data}")
                price = data.get("price")
                if price:
                    return float(price), "gold-api.com"
        except Exception as exc:
            logger.warning(f"gold-api.com failed: {exc}")

        # 2️⃣ metals-api.com (FREE TIER - 250 requests/month)
        try:
            logger.info("Trying metals-api.com...")
            r = SESSION.get(
                "https://api.metals.live/v1/spot/gold",
                timeout=10,
            )
            logger.info(f"metals-api response: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                logger.info(f"metals-api data: {data}")
                price = data.get("price")
                if price:
                    return float(price), "metals-api.live"
        except Exception as exc:
            logger.warning(f"metals-api failed: {exc}")

        # 3️⃣ Yahoo Finance
        for symbol in SYMBOLS["gold"]:
            try:
                logger.info(f"Trying Yahoo chart for {symbol}...")
                r = SESSION.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                    timeout=15,
                )
                logger.info(f"Yahoo {symbol} response: {r.status_code}")
                if r.status_code == 200:
                    result = r.json().get("chart", {}).get("result")
                    if result:
                        price = result[0].get("meta", {}).get("regularMarketPrice")
                        if price:
                            logger.info(f"Yahoo {symbol} price found: {price}")
                            return float(price), symbol
            except Exception as exc:
                logger.warning(f"Yahoo {symbol} failed: {exc}")

        # 4️⃣ Alpha Vantage (demo key - limited)
        try:
            logger.info("Trying Alpha Vantage...")
            r = SESSION.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol":   "GC=F",
                    "apikey":   ALPHA_VANTAGE_KEY,
                },
                timeout=10,
            )
            logger.info(f"Alpha Vantage response: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                logger.info(f"Alpha Vantage data: {data}")
                price = data.get("Global Quote", {}).get("05. price")
                if price:
                    logger.info(f"Alpha Vantage price found: {price}")
                    return float(price), "AlphaVantage"
        except Exception as exc:
            logger.warning(f"Alpha Vantage failed: {exc}")

        logger.error("All Gold price sources failed!")
        return None, None

    if asset == "btc":
        # 1️⃣ Binance
        try:
            logger.info("Trying Binance...")
            r = SESSION.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": "BTCUSDT"},
                timeout=10,
            )
            logger.info(f"Binance response: {r.status_code}")
            if r.status_code == 200:
                price = r.json().get("price")
                if price:
                    logger.info(f"Binance price found: {price}")
                    return float(price), "Binance"
        except Exception as exc:
            logger.warning(f"Binance failed: {exc}")

        # 2️⃣ Coingecko
        try:
            logger.info("Trying Coingecko...")
            r = SESSION.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            logger.info(f"Coingecko response: {r.status_code}")
            if r.status_code == 200:
                price = r.json().get("bitcoin", {}).get("usd")
                if price:
                    logger.info(f"Coingecko price found: {price}")
                    return float(price), "Coingecko"
        except Exception as exc:
            logger.warning(f"Coingecko failed: {exc}")

        # 3️⃣ Yahoo
        for symbol in SYMBOLS["btc"]:
            try:
                logger.info(f"Trying Yahoo chart for {symbol}...")
                r = SESSION.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                    timeout=15,
                )
                logger.info(f"Yahoo {symbol} response: {r.status_code}")
                if r.status_code == 200:
                    result = r.json().get("chart", {}).get("result")
                    if result:
                        price = result[0].get("meta", {}).get("regularMarketPrice")
                        if price:
                            logger.info(f"Yahoo {symbol} price found: {price}")
                            return float(price), symbol
            except Exception as exc:
                logger.warning(f"Yahoo {symbol} failed: {exc}")

        logger.error("All BTC price sources failed!")
        return None, None

    return None, None
