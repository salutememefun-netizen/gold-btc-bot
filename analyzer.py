import requests
import os
import pandas as pd
import numpy as np

# ============================================================
# KONFIGURASI
# ============================================================
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# ============================================================
# HARGA GOLD (XAUUSDc - Cent Account)
# ============================================================
# Broker anda guna XAUUSDc = XAUUSD × 100
# Jadi kita darab harga pasaran global dengan 100
GOLD_MULTIPLIER = 100

def get_price(symbol):
    s = str(symbol).upper()
    if s in ["GOLD", "GC=F", "XAUUSD", "XAUUSDc"]:
        return get_gold_price()
    elif s in ["BTC", "BTC-USD", "BTCUSD"]:
        return get_btc_price()
    return 0

def get_gold_price():
    """
    Ambil harga Gold dan darab dengan 100 untuk XAUUSDc.
    """
    # Cuba Finnhub dulu
    if FINNHUB_API_KEY:
        try:
            r = requests.get(
                f"https://finnhub.io/api/v1/quote?symbol=XAUUSD&token={FINNHUB_API_KEY}",
                timeout=10
            )
            p = r.json().get("c", 0)
            if p and float(p) > 0:
                # Darab dengan 100 untuk dapat harga XAUUSDc
                price = round(float(p) * GOLD_MULTIPLIER, 2)
                print(f"✅ Gold (XAUUSDc) dari Finnhub: ${price}")
                return price
        except Exception as e:
            print(f"⚠️ Finnhub gagal: {e}")

    # Cuba Yahoo Finance GC=F
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        data = r.json()
        p = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        # Darab dengan 100 untuk dapat harga XAUUSDc
        price = round(float(p) * GOLD_MULTIPLIER, 2)
        print(f"✅ Gold (XAUUSDc) dari Yahoo: ${price}")
        return price
    except Exception as e:
        print(f"⚠️ Yahoo gagal: {e}")

    print("❌ Semua sumber Gold gagal")
    return 0

def get_btc_price():
    """Ambil harga BTC (tiada multiplier)."""
    if FINNHUB_API_KEY:
        try:
            r = requests.get(
                f"https://finnhub.io/api/v1/quote?symbol=BINANCE:BTCUSDT&token={FINNHUB_API_KEY}",
                timeout=10
            )
            p = r.json().get("c", 0)
            if p and float(p) > 0:
                return round(float(p), 2)
        except:
            pass
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=10
        )
        return round(float(r.json()["bitcoin"]["usd"]), 2)
    except:
        pass
    return 0

def get_historical_data(symbol):
    """Ambil data sejarah untuk analisis teknikal."""
    sym = "GC=F" if str(symbol).upper() in ["GOLD", "GC=F", "XAUUSD", "XAUUSDc"] else "BTC-USD"
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=15m&range=5d",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        d = r.json()["chart"]["result"][0]
        closes = d["indicators"]["quote"][0]["close"]
        highs = d["indicators"]["quote"][0]["high"]
        lows = d["indicators"]["quote"][0]["low"]
        clean = [
            (closes[i], highs[i], lows[i])
            for i in range(len(closes))
            if closes[i] is not None and highs[i] is not None and lows[i] is not None
        ]
        if len(clean) < 20:
            return None
        c, h, l = zip(*clean)
        return pd.DataFrame({"close": list(c), "high": list(h), "low": list(l)})
    except:
        return None

def calculate_rsi(prices, period=14):
    try:
        if len(prices) < period + 1:
            return 50.0
        p = pd.Series(prices, dtype=float)
        d = p.diff()
        g = d.where(d > 0, 0.0)
        l = -d.where(d < 0, 0.0)
        rs = g.rolling(period).mean() / (l.rolling(period).mean() + 1e-10)
        return round((100 - 100 / (1 + rs)).dropna().iloc[-1], 2)
    except:
        return 50.0

def calculate_ema(prices, period):
    try:
        return round(float(pd.Series(prices, dtype=float).ewm(span=period, adjust=False).mean().iloc[-1]), 2)
    except:
        return 0.0

def calculate_bollinger(prices,
