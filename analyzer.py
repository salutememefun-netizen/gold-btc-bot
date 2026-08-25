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
    """Ambil harga Gold dari Finnhub atau Yahoo Finance."""
    # Cuba Finnhub
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

    # Cuba Yahoo Finance GC=F
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        headers = {"User-Agent": "Mozilla/5.0"}
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

    print("❌ Semua sumber Gold gagal")
    return 0

def get_btc_price():
    """Ambil harga BTC dari Finnhub atau CoinGecko."""
    # Cuba Finnhub
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

    # Cuba CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        r = requests.get(url, timeout=10)
        data = r.json()
        price = data["bitcoin"]["usd"]
        print(f"✅ BTC dari CoinGecko: ${price}")
        return round(float(price), 2)
    except Exception as e:
        print(f"⚠️ CoinGecko gagal: {e}")

    print("❌ Semua sumber BTC gagal")
    return 0

# ============================================================
# FUNGSI AMBIL DATA SEJARAH
# ============================================================

def get_historical_data(symbol, period="5d", interval="15m"):
    """Ambil data sejarah untuk analisis teknikal."""
    if str(symbol).upper() in ["GOLD", "GC=F", "XAUUSD"]:
        yahoo_symbols = ["GC=F"]
    elif str(symbol).upper() in ["BTC", "BTC-USD", "BTCUSD"]:
        yahoo_symbols = ["BTC-USD"]
    else:
        yahoo_symbols = [symbol]

    for yahoo_symbol in yahoo_symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            headers = {"User-Agent": "Mozilla/5.0"}
            params = {"interval": interval, "range": period}
            r = requests.get(url, headers=headers, params=params, timeout=15)
            data = r.json()

            result = data.get("chart", {}).get("result", None)
            if not result or len(result) == 0:
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
                continue

            clean = [
                (c, h, l, o, v if v else 0)
                for c, h, l, o, v in zip(closes, highs, lows, opens, volumes)
                if c is not None and h is not None and l is not None and o is not None
            ]

            if len(clean) < 20:
                continue

            c, h, l, o, v = zip(*clean)

            df = pd.DataFrame({
                "close": list(c),
                "high": list(h),
                "low": list(l),
                "open": list(o),
                "volume": list(v)
            })

            return df

        except Exception as e:
            continue

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

def calculate_bos(df):
    """Kira Break of Structure (BOS)."""
    try:
        if len(df) < 10:
            return None
        
        highs = df["high"].values
        lows = df["low"].values
        
        # Cari swing high dan swing low
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None
            
        # Cek BOS
        last_high = swing_highs[-1][1]
        prev_high = swing_highs[-2][1]
        last_low = swing_lows[-1][1]
        prev_low = swing_lows[-2][1]
        
        if last_high > prev_high:
            return "Bullish BOS (Pecah Resistance)"
        elif last_low < prev_low:
            return "Bearish BOS (Pecah Support)"
        else:
            return None
            
    except Exception as e:
        print(f"⚠️ Ralat BOS: {e}")
        return None

# ============================================================
# FUNGSI JANA SIGNAL
# ============================================================

def generate_signal(symbol, name):
    """Jana signal trading dengan analisis teknikal penuh."""
    price = get_price(symbol)
    if price == 0:
        return "❌ Gagal mengambil harga. Sila semak sambungan internet."

    df = get_historical_data(symbol)

    if df is None or len(df) < 20:
        return (
            f"{'🥇' if name == 'GOLD' else '₿'} *SIGNAL {name}*\n"
            f"💰 Harga: ${price}\n\n"
            f"⚠️ Data sejarah tidak mencukupi untuk analisis penuh.\n"
            f"Sila cuba semula dalam beberapa minit."
        )

    closes = df["close"].tolist()

    rsi = calculate_rsi(closes)
    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)
    bb_upper, bb_lower = calculate_bollinger(closes)
    supertrend = calculate_supertrend(df)
    bos = calculate_bos(df)

    # Tentukan trend dari EMA Crossover
    if ema9 > ema21:
        ema_trend = "BULLISH 🟢"
        ema_signal = "BUY"
    elif ema9 < ema21:
        ema_trend = "BEARISH 🔴"
        ema_signal = "SELL"
    else:
        ema_trend = "NEUTRAL 🟡"
        ema_signal = "HOLD"

    # Tentukan isyarat RSI
    if rsi >= 70:
        rsi_signal = "OVERBOUGHT ⚠️ (Pertimbangkan SELL)"
    elif rsi <= 30:
        rsi_signal = "OVERSOLD ⚠️ (Pertimbangkan BUY)"
    elif rsi >= 55:
        rsi_signal = "Bullish Zone"
    elif rsi <= 45:
        rsi_signal = "Bearish Zone"
    else:
        rsi_signal = "Neutral"

    # Tentukan posisi harga dalam Bollinger Band
    if price > bb_upper:
        bb_status = "Di atas Upper Band ⚠️"
    elif price < bb_lower:
        bb_status = "Di bawah Lower Band ⚠️"
    else:
        bb_status = "Di dalam Band ✅"

    # Keputusan akhir signal
    buy_score = 0
    sell_score = 0

    if ema_signal == "BUY":
        buy_score += 1
    elif ema_signal == "SELL":
        sell_score += 1

    if rsi < 45:
        sell_score += 1
    elif rsi > 55:
        buy_score += 1

    if supertrend == "BULLISH 🟢":
        buy_score += 1
    else:
        sell_score += 1

    if buy_score > sell_score:
        final_signal = "🟢 BUY"
        final_trend = "BULLISH"
    elif sell_score > buy_score:
        final_signal = "🔴 SELL"
        final_trend = "BEARISH"
    else:
        final_signal = "🟡 HOLD"
        final_trend = "NEUTRAL"

    # Kira zon entry, SL, TP
    if name == "GOLD":
        sl_pips = 10
        tp_pips = 20
    else:
        sl_pips = 300
        tp_pips = 600

    if "BUY" in final_signal:
        entry = price
        sl = round(price - sl_pips, 2)
        tp = round(price + tp_pips, 2)
    elif "SELL" in final_signal:
        entry = price
        sl = round(price + sl_pips, 2)
        tp = round(price - tp_pips, 2)
    else:
        entry = price
        sl = round(price - sl_pips, 2)
        tp = round(price + tp_pips, 2)

    # Format mesej signal
    bos_msg = f"- BOS: {bos}" if bos else "- BOS: Neutral"
    
    if name == "GOLD":
        msg = (
            f"🥇 *SIGNAL GOLD (XAUUSD)*\n"
            f"💰 Harga: ${price}\n\n"
            f"⚡ *Supertrend:* {supertrend}\n\n"
            f"📊 *RSI (14):* {rsi}\n"
            f"   └ {rsi_signal}\n\n"
            f"📉 *Bollinger Band:*\n"
            f"   Upper: ${bb_upper} | Lower: ${bb_lower}\n"
            f"   Status: {bb_status}\n\n"
            f"📈 *EMA Crossover:*\n"
            f"   EMA9: ${ema9} | EMA21: ${ema21}\n"
            f"   Trend: {ema_trend}\n\n"
            f"{bos_msg}\n\n"
            f"🎯 *SIGNAL AKHIR: {final_signal}*\n\n"
            f"🟢 *ZON BUY (LONG):*\n"
            f"   Entry: ${entry}\n"
