import requests
import os
import time

# --- KONFIGURASI API ---
# Ambil dari Environment Variable (Railway)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# Simbol yang betul untuk Spot Gold dan BTC
GOLD_SYMBOL = "XAUUSD"
BTC_SYMBOL = "BTCUSD"

def get_price(symbol):
    """
    Mengambil harga real-time.
    Parameter symbol:
      - "GOLD", "GC=F", "XAUUSD" -> Akan ambil harga Spot Gold (XAUUSD)
      - "BTC", "BTC-USD", "BTCUSD" -> Akan ambil harga Bitcoin (BTCUSD)
    """
    s = str(symbol).upper()
    
    if s in ["GOLD", "GC=F", "XAUUSD"]:
        return get_gold_price()
    elif s in ["BTC", "BTC-USD", "BTCUSD"]:
        return get_btc_price()
    else:
        print(f"⚠️ Simbol tidak dikenali: {symbol}")
        return 0

def get_gold_price():
    """
    Ambil harga Spot Gold (XAUUSD).
    Cuba Finnhub dulu, fallback ke Yahoo Finance jika gagal.
    """
    # Cuba Finnhub dulu
    if FINNHUB_API_KEY and "your" not in FINNHUB_API_KEY.lower():
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={GOLD_SYMBOL}&token={FINNHUB_API_KEY}"
            response = requests.get(url, timeout=10)
            data = response.json()
            price = data.get("c", 0)
            if price > 0:
                print(f"✅ Harga Gold dari Finnhub: ${price}")
                return round(price, 2)
        except Exception as e:
            print(f"⚠️ Finnhub gagal: {e}, cuba Yahoo Finance...")
    
    # Fallback ke Yahoo Finance (GC=F)
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        print(f"✅ Harga Gold dari Yahoo: ${price}")
        return round(price, 2)
    except Exception as e:
        print(f"❌ Gagal ambil harga Gold: {e}")
        return 0

def get_btc_price():
    """
    Ambil harga BTC.
    Cuba Finnhub dulu, fallback ke CoinGecko jika gagal.
    """
    if FINNHUB_API_KEY and "your" not in FINNHUB_API_KEY.lower():
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={BTC_SYMBOL}&token={FINNHUB_API_KEY}"
            response = requests.get(url, timeout=10)
            data = response.json()
            price = data.get("c", 0)
            if price > 0:
                print(f"✅ Harga BTC dari Finnhub: ${price}")
                return round(price, 2)
        except Exception as e:
            print(f"⚠️ Finnhub gagal: {e}, cuba CoinGecko...")
    
    # Fallback ke CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        data = response.json()
        price = data["bitcoin"]["usd"]
        print(f"✅ Harga BTC dari CoinGecko: ${price}")
        return round(price, 2)
    except Exception as e:
        print(f"❌ Gagal ambil harga BTC: {e}")
        return 0

def generate_signal(symbol, name):
    """
    Jana signal trading.
    Pastikan semua fungsi ini diexport untuk bot.py.
    """
    price = get_price(symbol)
    
    if price == 0:
        return "❌ Gagal mengambil harga. Sila semak API Key atau sambungan internet."

    # --- LOGIK ANALISIS TEKNIKAL (CONTOH) ---
    # Anda perlu tambah kod RSI, EMA, Bollinger di sini
    # Untuk sekarang, guna logik mudah berdasarkan harga
    
    if name == "GOLD":
        # Contoh logik (gantikan dengan analisis sebenar)
        if price > 2700:
            trend = "BULLISH 🟢"
            signal = "BUY"
            rsi = 65
        elif price < 2600:
            trend = "BEARISH 🔴"
            signal = "SELL"
            rsi = 35
        else:
            trend = "NEUTRAL 🟡"
            signal = "HOLD"
            rsi = 50
            
        msg = (
            f"🥇 *SIGNAL {name} (XAUUSD)*\n"
            f"💰 Harga: ${price}\n\n"
            f"📊 *Analisis:*\n"
            f"- Trend: {trend}\n"
            f"- RSI: {rsi}\n"
            f"- Isyarat: {signal}\n\n"
            f"📡 Sumber: Finnhub/Spot Gold"
        )
    else:  # BTC
        if price > 65000:
            trend = "BULLISH 🟢"
            signal = "BUY"
            rsi = 62
        elif price < 60000:
            trend = "BEARISH 🔴"
            signal = "SELL"
            rsi = 38
        else:
            trend = "NEUTRAL 🟡"
            signal = "HOLD"
            rsi = 50
            
        msg = (
            f"₿ *SIGNAL {name} (BTC)*\n"
            f"💰 Harga: ${price}\n\n"
            f"📊 *Analisis:*\n"
            f"- Trend: {trend}\n"
            f"- RSI: {rsi}\n"
            f"- Isyarat: {signal}"
        )
        
    return msg

def check_zone_alert(symbol, name):
    """
    Semak jika harga masuk zon alert.
    """
    price = get_price(symbol)
    if price == 0:
        return False, None, 0, 0, 0
    
    # --- LOGIK ZON ANDA DI SINI ---
    is_active = False
    zone_type = None
    entry_price = 0
    tp = 0
    sl = 0
    
    if name == "GOLD":
        # Contoh: Zon BUY 2695-2705, Zon SELL 2590-2600
        if 2695 <= price <= 2705:
            is_active = True
            zone_type = "BUY"
            entry_price = price
            tp = price + 15
            sl = price - 10
        elif 2590 <= price <= 2600:
            is_active = True
            zone_type = "SELL"
            entry_price = price
            tp = price - 15
            sl = price + 10
    elif name == "BTC":
        if 64800 <= price <= 65200:
            is_active = True
            zone_type = "BUY"
            entry_price = price
            tp = price + 500
            sl = price - 300
        elif 60000 <= price <= 60500:
            is_active = True
            zone_type = "SELL"
            entry_price = price
            tp = price - 500
            sl = price + 300
            
    return is_active, zone_type, entry_price, tp, sl
