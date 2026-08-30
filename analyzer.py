import requests
import os
import pandas as pd
import numpy as np

# ============================================================
# KONFIGURASI
# ============================================================
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# BEZA HARGA ANTARA BOT DAN MT5 ANDA
# Nilai ini kena diupdate manual di Railway Variables
# Contoh: Jika harga bot $4691 dan MT5 $4644, beza = 47
# Guna format float: 47.0
PRICE_OFFSET = float(os.getenv("PRICE_OFFSET", "46.77"))

# ============================================================
# FUNGSI AMBIL HARGA
# ============================================================

def get_price(symbol):
    s = str(symbol).upper()
    if s in ["GOLD", "GC=F", "XAUUSD", "XAUUSDC"]:
        return get_gold_price()
    elif s in ["BTC", "BTC-USD", "BTCUSD"]:
        return get_btc_price()
    return 0

def get_gold_price():
    """Ambil harga Gold dari Finnhub/Yahoo."""
    if FINNHUB_API_KEY:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol=XAUUSD&token={FINNHUB_API_KEY}", timeout=10)
            p = r.json().get("c", 0)
            if p and float(p) > 0:
                price = round(float(p), 2)
                print(f"✅ Gold dari Finnhub: ${price}")
                return price
        except Exception as e:
            print(f"⚠️ Finnhub gagal: {e}")
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/f
