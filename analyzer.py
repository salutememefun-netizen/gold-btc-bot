import requests
import os
import time
import random

# --- KONFIGURASI API ---
# Gantikan "your_finnhub_api_key_here" dengan API Key Finnhub anda, 
# atau pastikan anda sudah set environment variable: export FINNHUB_API_KEY="key_anda"
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "your_finnhub_api_key_here")

# Simbol yang betul untuk Spot Gold (XAUUSD) dan Bitcoin (BTCUSD) di Finnhub
# Ini adalah simbol yang digunakan oleh broker Forex, bukan Futures.
GOLD_SYMBOL = "XAUUSD"
BTC_SYMBOL = "BTCUSD"

def get_price(symbol):
    """
    Mengambil harga real-time dari Finnhub.
    Parameter symbol:
      - "GOLD", "GC=F", "XAUUSD" -> Akan ambil harga Spot Gold (XAUUSD)
      - "BTC", "BTC-USD", "BTCUSD" -> Akan ambil harga Bitcoin (BTCUSD)
    """
    # Normalize input symbol
    s = str(symbol).upper()
    
    if s in ["GOLD", "GC=F", "XAUUSD"]:
        return get_gold_price_finnhub()
    elif s in ["BTC", "BTC-USD", "BTCUSD"]:
        return get_btc_price_finnhub()
    else:
        print(f"⚠️ Simbol tidak dikenali: {symbol}")
        return 0

def get_gold_price_finnhub():
    """
    Ambil harga Spot Gold (XAUUSD) dari Finnhub.
    Finnhub API: https://finnhub.io/api/v1/quote
    """
    if not FINNHUB_API_KEY or "your_finnhub" in FINNHUB_API_KEY.lower():
        # Fallback jika tiada API Key (hanya untuk testing/pencegahan error)
        print("⚠️ AMARAN: API Key Finnhub tidak diset dengan betul. Menggunakan harga sample.")
        return 2688.50 

    url = f"https://finnhub.io/api/v1/quote?symbol={GOLD_SYMBOL}&token={FINNHUB_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Finnhub return format:
        # 'c': current price (harga terkini)
        # 'h': high
        # 'l': low
        # 'o': open
        # 'pc': previous close
        # 't': timestamp
        
        current_price = data.get("c")
        
        if current_price is None or current_price == 0:
            # Jika tiada data terkini, cuba guna high/low sebagai fallback (jarang berlaku)
            current_price = data.get("h", 0)
            if current_price == 0:
                raise ValueError("Harga tidak dapat diperolehi dari Finnhub.")
        
        # Round kepada 2 tempat perpuluhan (standard untuk Gold)
        return round(float(current_price), 2)
        
    except Exception as e:
        print(f"❌ Ralat mengambil harga Gold dari Finnhub: {e}")
        # Return harga sample jika error untuk elak bot crash
        return 0

def get_btc_price_finnhub():
    """
    Ambil harga Bitcoin (BTCUSD) dari Finnhub.
    """
    if not FINNHUB_API_KEY or "your_finnhub" in FINNHUB_API_KEY.lower():
        return 64500.00 # Harga sample

    url = f"https://finnhub.io/api/v1/quote?symbol={BTC_SYMBOL}&token={FINNHUB_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current_price = data.get("c")
        
        if current_price is None or current_price == 0:
            raise ValueError("Harga BTC tidak dapat diperolehi dari Finnhub.")
        
        return round(float(current_price), 2)
        
    except Exception as e:
        print(f"❌ Ralat mengambil harga BTC dari Finnhub: {e}")
        return 0

def generate_signal(symbol, name):
    """
    Fungsi untuk menjana signal trading.
    Pastikan anda masukkan logik analisis teknikal sebenar anda di sini.
    Kod di bawah adalah contoh struktur dengan harga dari Finnhub.
    """
    price = get_price(symbol)
    
    if price == 0:
        return "❌ Gagal mengambil harga. Sila semak API Key Finnhub atau sambungan internet."

    # --- LOGIK ANALISIS TEKNIKAL ANDA DI SINI ---
    # Di sini anda perlu masukkan kod untuk kira RSI, EMA, Supertrend, dll.
    # Contoh: Anda mungkin perlu ambil data sejarah (candles) dari Finnhub juga.
    # Contoh output dummy di bawah:
    
    # Contoh: Logik mudah (GANTIKAN DENGAN LOGIK SEBENAR ANDA)
    # Jika harga > 2700 -> BUY, jika < 2600 -> SELL, else NEUTRAL
    if name == "GOLD":
        if price > 2700:
            trend = "BULLISH 🟢"
            signal = "BUY"
            rsi = 65.2
        elif price < 2600:
            trend = "BEARISH 🔴"
            signal = "SELL"
            rsi = 35.8
        else:
            trend = "NEUTRAL 🟡"
            signal = "HOLD"
            rsi = 50.0
            
        msg = (
            f"🥇 *SIGNAL {name} (XAUUSD)*\n"
            f"💰 Harga Semasa: ${price}\n\n"
            f"📊 *Analisis Teknikal:*\n"
            f"- Trend: {trend}\n"
            f"- RSI: {rsi}\n"
            f"- Isyarat: {signal}\n\n"
            f"📡 *Sumber Data:* Finnhub (Spot Gold)\n"
            f"⚠️ *Nota:* Harga ini adalah Spot Gold yang hampir sama dengan broker MT5 anda."
        )
    else: # BTC
        if price > 65000:
            trend = "BULLISH 🟢"
            signal = "BUY"
            rsi = 62.5
        elif price < 60000:
            trend = "BEARISH 🔴"
            signal = "SELL"
            rsi = 38.2
        else:
            trend = "NEUTRAL 🟡"
            signal = "HOLD"
            rsi = 49.0
            
        msg = (
            f"₿ *SIGNAL {name} (BTC)*\n"
            f"💰 Harga Semasa: ${price}\n\n"
            f"📊 *Analisis Teknikal:*\n"
            f"- Trend: {trend}\n"
            f"- RSI: {rsi}\n"
            f"- Isyarat: {signal}\n\n"
            f"📡 *Sumber Data:* Finnhub"
        )
        
    return msg

def check_zone_alert(symbol, name):
    """
    Fungsi untuk menyemak jika harga masuk zon alert.
    Pastikan ia menggunakan harga dari get_price() yang baru.
    """
    price = get_price(symbol)
    if price == 0:
        return False, None, 0, 0, 0
    
    # --- LOGIK ALERT ZON ANDA DI SINI ---
    # Contoh: Alert jika harga masuk zon BUY (> 2700) atau SELL (< 2600)
    # Gantikan dengan logik sebenar anda (contoh: harga dekat dengan Support/Resistance)
    
    is_active = False
    zone_type = None
    entry_price = 0
    tp = 0
    sl = 0
    
    if name == "GOLD":
        if price >= 2695 and price <= 2705: # Contoh zon BUY
            is_active = True
            zone_type = "BUY"
            entry_price = price
            tp = price + 15
            sl = price - 10
        elif price >= 2590 and price <= 2600: # Contoh zon SELL
            is_active = True
            zone_type = "SELL"
            entry_price = price
            tp = price - 15
            sl = price + 10
    elif name == "BTC":
        if price >= 64800 and price <= 65200:
            is_active = True
            zone_type = "BUY"
            entry_price = price
            tp = price + 500
            sl = price - 300
        elif price >= 60000 and price <= 60500:
            is_active = True
            zone_type = "SELL"
            entry_price = price
            tp = price - 500
            sl = price + 300
            
    return is_active, zone_type, entry_price, tp, sl
