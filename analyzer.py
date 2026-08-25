import requests
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================================
# KONFIGURASI
# ============================================================
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# ============================================================
# FUNGSI AMBIL HARGA SEMASA
# ============================================================

def get_price(symbol):
    s = str(symbol).upper()
    if s in ["GOLD", "GC=F", "XAUUSD"]:
        return get_gold_price()
    elif s in ["BTC", "BTC-USD", "BTCUSD"]:
        return get_btc_price()
    return 0

def get_gold_price():
    """
    Cuba pelbagai sumber untuk harga Gold.
    """
    # Sumber 1: Finnhub
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol=XAUUSD&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=10)
            data = r.json()
            price = data.get("c", 0)
            if price and float(price) > 0:
                print(f"✅ Gold dari Finnhub: ${price}")
                return round(float(price), 2)
        except Exception as e:
            print(f"⚠️ Finnhub gagal: {e}")

    # Sumber 2: Yahoo Finance GC=F (Futures - paling stabil)
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        params = {"interval": "1m", "range": "1d"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        
        result = data.get("chart", {}).get("result", None)
        if result and len(result) > 0:
            price = result[0].get("meta", {}).get("regularMarketPrice", 0)
            if price and float(price) > 0:
                print(f"✅ Gold dari Yahoo GC=F: ${price}")
                return round(float(price), 2)
    except Exception as e:
        print(f"⚠️ Yahoo GC=F gagal: {e}")

    # Sumber 3: Metal Price API (percuma, tiada key)
    try:
        url = "https://api.metalpriceapi.com/v1/latest?api_key=demo&base=XAU&currencies=USD"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("success"):
            price = 1 / data["rates"]["USD"]
            print(f"✅ Gold dari MetalPriceAPI: ${price}")
            return round(float(price), 2)
    except Exception as e:
        print(f"⚠️ MetalPriceAPI gagal: {e}")

    print("❌ Semua sumber Gold gagal")
    return 0

def get_btc_price():
    """
    Cuba pelbagai sumber untuk harga BTC.
    """
    # Sumber 1: Finnhub
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol=BINANCE:BTCUSDT&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=10)
            data = r.json()
            price = data.get("c", 0)
            if price and float(price) > 0:
                print(f"✅ BTC dari Finnhub: ${price}")
                return round(float(price), 2)
        except Exception as e:
            print(f"⚠️ Finnhub BTC gagal: {e}")

    # Sumber 2: CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        r = requests.get(url, timeout=10)
        data = r.json()
        price = data["bitcoin"]["usd"]
        print(f"✅ BTC dari CoinGecko: ${price}")
        return round(float(price), 2)
    except Exception as e:
        print(f"⚠️ CoinGecko gagal: {e}")

    # Sumber 3: Yahoo Finance BTC-USD
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {"interval": "1m", "range": "1d"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        result = data.get("chart", {}).get("result", None)
        if result and len(result) > 0:
            price = result[0].get("meta", {}).get("regularMarketPrice", 0)
            if price and float(price) > 0:
                print(f"✅ BTC dari Yahoo: ${price}")
                return round(float(price), 2)
    except Exception as e:
        print(f"⚠️ Yahoo BTC gagal: {e}")

    print("❌ Semua sumber BTC gagal")
    return 0

# ============================================================
# FUNGSI AMBIL DATA SEJARAH
# ============================================================

def get_historical_data(symbol, period="5d", interval="15m"):
    """
    Ambil data sejarah dari Yahoo Finance untuk analisis teknikal.
    """
    # Tentukan simbol Yahoo
    if str(symbol).upper() in ["GOLD", "GC=F", "XAUUSD"]:
        yahoo_symbols = ["GC=F"]  # GC=F lebih stabil dari XAUUSD=X
    elif str(symbol).upper() in ["BTC", "BTC-USD", "BTCUSD"]:
        yahoo_symbols = ["BTC-USD"]
    else:
        yahoo_symbols = [symbol]

    for yahoo_symbol in yahoo_symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json"
            }
            params = {"interval": interval, "range": period}
            r = requests.get(url, headers=headers, params=params, timeout=15)
            data = r.json()

            chart = data.get("chart", {})
            result = chart.get("result", None)
            
            if not result or len(result) == 0:
                print(f"⚠️ Tiada data untuk {yahoo_symbol}")
                continue

            result = result[0]
            timestamps = result.get("timestamp", [])
            indicators = result.get("indicators", {})
            quote = indicators.get("quote", [{}])[0]
            
            closes = quote.get("close", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            opens = quote.get("open", [])
            volumes = quote.get("volume", [])

            if not closes or len(closes) < 20:
                print(f"⚠️ Data tidak mencukupi untuk {yahoo_symbol}: {len(closes)} candles")
                continue

            # Bersihkan data (buang None)
            clean = [
                (c, h, l, o, v if v else 0)
                for c, h, l, o, v in zip(closes, highs, lows, opens, volumes)
                if c is not None and h is not None and l is not None and o is not None
            ]

            if len(clean) < 20:
                print(f"⚠️ Data bersih tidak mencukupi: {len(clean)} candles")
                continue

            c, h, l, o, v = zip(*clean)

            df = pd.DataFrame({
                "close": list(c),
                "high": list(h),
                "low": list(l),
                "open": list(o),
                "volume": list(v)
            })

            print(f"✅ Data sejarah berjaya: {len(df)} candles dari {yahoo_symbol}")
            return df

        except Exception as e:
            print(f"⚠️ Gagal ambil data {yahoo_symbol}: {e}")
            continue

    print(f"❌ Gagal ambil semua data sejarah untuk {symbol}")
    return None

# ============================================================
# FUNGSI ANALISIS TEKNIKAL
# ============================================================

def calculate_rsi(prices, period=14):
    """Kira RSI."""
    try:
        if len(prices) < period + 1:
            return 50.0
        prices = pd.Series(prices, dtype=float)
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.dropna().iloc[-1]
        return round(float(val), 2)
    except Exception as e:
        print(f"⚠️ Ralat RSI: {e}")
        return 50.0

def calculate_ema(prices, period):
    """Kira EMA."""
    try:
        prices = pd.Series(prices, dtype=float)
        ema = prices.ewm(span=period, adjust=False).mean()
        return round(float(ema.iloc[-1]), 2)
    except Exception as e:
        print(f"⚠️ Ralat EMA: {e}")
        return 0.0

def calculate_bollinger(prices, period=20):
    """Kira Bollinger Bands."""
    try:
        prices = pd.Series(prices, dtype=float)
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = (sma + (std * 2)).dropna().iloc[-1]
        lower = (sma - (std * 2)).dropna().iloc[-1]
        return round(float(upper), 2), round(float(lower), 2)
    except Exception as e:
        print(f"⚠️ Ralat Bollinger: {e}")
        return 0.0, 0.0

def calculate_supertrend(df, period=10, multiplier=3):
    """Kira Supertrend."""
    try:
        if len(df) < period + 1:
            return "NEUTRAL 🟡"

        high = pd.Series(df["high"].values, dtype=float)
        low = pd.Series(df["low"].values, dtype=float)
        close = pd.Series(df["close"].values, dtype=float)

        # ATR
        hl = high - low
        hc = (high - close.shift(1)).abs()
        lc = (low - close.shift(1)).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        upper_band = (high + low) / 2 + multiplier * atr
        lower_band = (high + low) / 2 - multiplier * atr

        direction = [1] * len(close)

        for i in range(1, len(close)):
            if pd.isna(atr.iloc[i]):
                direction[i] = direction[i-1]
                continue
            if close.iloc[i] > upper_band.iloc[i-1]:
                direction[i] = 1
            elif close.iloc[i] < lower_band.iloc[i-1]:
                direction[i] = -1
            else:
                direction[i] = direction[i-1]

        latest = direction[-1]
        return "BULLISH 🟢" if latest == 1 else "BEARISH 🔴"

    except Exception as e:
        print(f"⚠️ Ralat Supertrend: {e}")
        return "NEUTRAL 🟡"

def calculate_bos
