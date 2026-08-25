import requests
import os
import pandas as pd
import numpy as np

# ============================================================
# KONFIGURASI
# ============================================================
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# ============================================================
# FUNGSI AMBIL HARGA
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
    Cuba Finnhub dulu, fallback ke Yahoo Finance.
    Harga yang dipaparkan adalah harga pasaran standard (XAUUSD).
    Broker anda mungkin tunjuk harga berbeza (contoh: $4,630)
    disebabkan jenis kontrak, tapi TREND dan ISYARAT adalah sama.
    """
    # Cuba Finnhub
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol=XAUUSD&token={FINNHUB_API_KEY}"
            response = requests.get(url, timeout=10)
            data = response.json()
            price = data.get("c", 0)
            if price and price > 0:
                print(f"✅ Gold dari Finnhub: ${price}")
                return round(float(price), 2)
        except Exception as e:
            print(f"⚠️ Finnhub gagal: {e}")

    # Fallback ke Yahoo Finance
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD=X?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        print(f"✅ Gold dari Yahoo (XAUUSD=X): ${price}")
        return round(float(price), 2)
    except Exception as e:
        print(f"⚠️ Yahoo XAUUSD=X gagal: {e}")

    # Fallback ke GC=F
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        print(f"✅ Gold dari Yahoo (GC=F): ${price}")
        return round(float(price), 2)
    except Exception as e:
        print(f"❌ Semua sumber Gold gagal: {e}")
        return 0

def get_btc_price():
    """
    Cuba Finnhub dulu, fallback ke CoinGecko.
    """
    # Cuba Finnhub
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol=BINANCE:BTCUSDT&token={FINNHUB_API_KEY}"
            response = requests.get(url, timeout=10)
            data = response.json()
            price = data.get("c", 0)
            if price and price > 0:
                print(f"✅ BTC dari Finnhub: ${price}")
                return round(float(price), 2)
        except Exception as e:
            print(f"⚠️ Finnhub BTC gagal: {e}")

    # Fallback ke CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        data = response.json()
        price = data["bitcoin"]["usd"]
        print(f"✅ BTC dari CoinGecko: ${price}")
        return round(float(price), 2)
    except Exception as e:
        print(f"❌ Semua sumber BTC gagal: {e}")
        return 0

# ============================================================
# FUNGSI AMBIL DATA SEJARAH (UNTUK ANALISIS TEKNIKAL)
# ============================================================

def get_historical_data(symbol, period="5d", interval="15m"):
    """
    Ambil data sejarah dari Yahoo Finance untuk kira RSI, EMA, dll.
    """
    try:
        if symbol in ["GOLD", "GC=F", "XAUUSD"]:
            yahoo_symbol = "XAUUSD=X"
        elif symbol in ["BTC", "BTC-USD"]:
            yahoo_symbol = "BTC-USD"
        else:
            yahoo_symbol = symbol

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval={interval}&range={period}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        highs = result["indicators"]["quote"][0]["high"]
        lows = result["indicators"]["quote"][0]["low"]
        volumes = result["indicators"]["quote"][0].get("volume", [0] * len(closes))

        # Bersihkan data (buang None)
        clean_data = [
            (t, c, h, l, v)
            for t, c, h, l, v in zip(timestamps, closes, highs, lows, volumes)
            if c is not None and h is not None and l is not None
        ]

        if not clean_data:
            return None

        timestamps, closes, highs, lows, volumes = zip(*clean_data)

        df = pd.DataFrame({
            "close": list(closes),
            "high": list(highs),
            "low": list(lows),
            "volume": list(volumes)
        })

        return df

    except Exception as e:
        print(f"❌ Gagal ambil data sejarah: {e}")
        return None

# ============================================================
# FUNGSI ANALISIS TEKNIKAL
# ============================================================

def calculate_rsi(prices, period=14):
    """Kira RSI (Relative Strength Index)."""
    try:
        if len(prices) < period + 1:
            return 50.0

        prices = pd.Series(prices)
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi.iloc[-1], 2)
    except Exception as e:
        print(f"⚠️ Ralat RSI: {e}")
        return 50.0

def calculate_ema(prices, period):
    """Kira EMA (Exponential Moving Average)."""
    try:
        prices = pd.Series(prices)
        ema = prices.ewm(span=period, adjust=False).mean()
        return round(ema.iloc[-1], 2)
    except Exception as e:
        print(f"⚠️ Ralat EMA: {e}")
        return 0

def calculate_bollinger(prices, period=20):
    """Kira Bollinger Bands."""
    try:
        prices = pd.Series(prices)
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return round(upper.iloc[-1], 2), round(lower.iloc[-1], 2)
    except Exception as e:
        print(f"⚠️ Ralat Bollinger: {e}")
        return 0, 0

def calculate_supertrend(df, period=10, multiplier=3):
    """Kira Supertrend."""
    try:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Average True Range (ATR)
        hl = high - low
        hc = abs(high - close.shift(1))
        lc = abs(low - close.shift(1))
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        # Upper & Lower Band
        upper_band = ((high + low) / 2) + (multiplier * atr)
        lower_band = ((high + low) / 2) - (multiplier * atr)

        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)

        for i in range(1, len(df)):
            if close.iloc[i] > upper_band.iloc[i - 1]:
                direction.iloc[i] = 1  # Bullish
            elif close.iloc[i] < lower_band.iloc[i - 1]:
                direction.iloc[i] = -1  # Bearish
            else:
                direction.iloc[i] = direction.iloc[i - 1]

        latest_direction = direction.iloc[-1]
        return "BULLISH 🟢" if latest_direction == 1 else "BEARISH 🔴"

    except Exception as e:
        print(f"⚠️ Ralat Supertrend: {e}")
        return "NEUTRAL 🟡"

# ============================================================
# FUNGSI JANA SIGNAL
# ============================================================

def generate_signal(symbol, name):
    """
    Jana signal trading dengan analisis teknikal penuh.
    """
    # Ambil harga semasa
    price = get_price(symbol)
    if price == 0:
        return "❌ Gagal mengambil harga. Sila semak sambungan internet."

    # Ambil data sejarah untuk analisis
    df = get_historical_data(symbol)

    if df is None or len(df) < 20:
        # Jika tiada data sejarah, buat signal ringkas
        return _generate_simple_signal(price, name)

    closes = df["close"].tolist()

    # Kira semua indikator teknikal
    rsi = calculate_rsi(closes)
    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)
    bb_upper, bb_lower = calculate_bollinger(closes)
    supertrend = calculate_supertrend(df)

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
            f"🎯 *SIGNAL AKHIR: {final_signal}*\n\n"
            f"🟢 *ZON BUY (LONG):*\n"
            f"   Entry: ${entry}\n"
            f"   Stop Loss: ${sl}\n"
            f"   Take Profit: ${tp}\n\n"
            f"⚠️ *NOTA PENTING:*\n"
            f"Harga di atas adalah harga pasaran global.\n"
            f"Sila semak harga di MT5 anda sebelum entry.\n"
            f"Gunakan signal (BUY/SELL) & aras SL/TP sebagai panduan.\n\n"
            f"📡 Sumber: Finnhub/Yahoo Finance"
        )
    else:
        msg = (
            f"₿ *SIGNAL BTC (BTCUSD)*\n"
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
            f"🎯 *SIGNAL AKHIR: {final_signal}*\n\n"
            f"🟢 *ZON BUY (LONG):*\n"
            f"   Entry: ${entry}\n"
            f"   Stop Loss: ${sl}\n"
            f"   Take Profit: ${tp}\n\n"
            f"📡 Sumber: Finnhub/Yahoo Finance"
        )

    return msg

def _generate_simple_signal(price, name):
    """
    Signal ringkas jika tiada data sejarah.
    """
    msg = (
        f"{'🥇' if name == 'GOLD' else '₿'} *SIGNAL {name}*\n"
        f"💰 Harga: ${price}\n\n"
        f"⚠️ Data sejarah tidak mencukupi untuk analisis penuh.\n"
        f"Sila cuba semula dalam beberapa minit."
    )
    return msg

# ============================================================
# FUNGSI ALERT ZON
# ============================================================

def check_zone_alert(symbol, name):
    """
    Semak jika harga masuk zon alert.
    Menggunakan analisis teknikal untuk tentukan zon.
    """
    price = get_price(symbol)
    if price == 0:
        return False, None, 0, 0, 0

    df = get_historical_data(symbol)

    if df is None or len(df) < 20:
        return False, None, 0, 0, 0

    closes = df["close"].tolist()
    rsi = calculate_rsi(closes)
    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)
    supertrend = calculate_supertrend(df)

    is_active = False
    zone_type = None
    entry_price = 0
    tp = 0
    sl = 0

    if name == "GOLD":
        sl_pips = 10
        tp_pips = 20
    else:
        sl_pips = 300
        tp_pips = 600

    # Alert BUY: RSI oversold + EMA bullish + Supertrend bullish
    if rsi <= 35 and ema9 > ema21 and supertrend == "BULLISH 🟢":
        is_active = True
        zone_type = "BUY"
        entry_price = price
        tp = round(price + tp_pips, 2)
        sl = round(price - sl_pips, 2)

    # Alert SELL: RSI overbought + EMA bearish + Supertrend bearish
    elif rsi >= 65 and ema9 < ema21 and supertrend == "BEARISH 🔴":
        is_active = True
        zone_type = "SELL"
        entry_price = price
        tp = round(price - tp_pips, 2)
        sl = round(price + sl_pips, 2)

    return is_active, zone_type, entry_price, tp, sl
