#!/usr/bin/env python3
"""
Helper functions - Auto detect DB & API
"""

import requests
import logging
import math
import os
from typing import Optional, List, Tuple, Dict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# DATABASE: Auto detect dari Railway
# ============================================
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    logger.warning("⚠️ DATABASE_URL tidak dijumpai! Cuba nama lain...")
    # Cuba nama lain yang kadang-kadang Railway guna
    DB_URL = (
        os.getenv("POSTGRES_URL") or 
        os.getenv("POSTGRES_HOST") or 
        os.getenv("DATABASE") or 
        ""
    )

def get_db_connection():
    if not DB_URL:
        logger.error("❌ TIDAK ADA DATABASE_URL! Sila semak Railway Variables.")
        return None
    
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        logger.info("✅ Berhasil sambung ke PostgreSQL!")
        return conn
    except Exception as e:
        logger.error(f"❌ Gagal sambung DB: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id BIGINT PRIMARY KEY,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Table 'subscribers' di-check/dibuat.")
        return True
    except Exception as e:
        logger.error(f"❌ Gagal init table: {e}")
        return False

def add_subscriber_db(chat_id: int) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO subscribers (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING",
            (chat_id,)
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Error add subscriber: {e}")
        return False

def remove_subscriber_db(chat_id: int) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM subscribers WHERE chat_id = %s", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Error remove subscriber: {e}")
        return False

def get_all_subscribers() -> list:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM subscribers")
        subscribers = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return subscribers
    except Exception as e:
        logger.error(f"❌ Error get subscribers: {e}")
        return []

# ============================================
# API: Harga Live
# ============================================
def get_btc_price() -> Optional[float]:
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=5)
        return resp.json()["bitcoin"]["usd"]
    except Exception as e:
        logger.error(f"❌ Error BTC: {e}")
        return None

def get_gold_price() -> Optional[float]:
    try:
        url = "https://xaus.com/api/v1/spot"
        resp = requests.get(url, timeout=5)
        return resp.json()["spot_usd_oz"]
    except Exception as e:
        logger.error(f"❌ Error GOLD: {e}")
        return None

def get_binance_candles(symbol: str, interval: str = "1h", limit: int = 100) -> Optional[List[Dict]]:
    if symbol == "GOLD":
        try:
            resp = requests.get("https://xaus.com/api/v1/history", timeout=10)
            data = resp.json()
            points = data.get("points", [])
            candles = []
            for p in points[-limit:]:
                candles.append({
                    "open": p.get("o", p["c"]),
                    "high": p.get("h", p["c"]),
                    "low": p.get("l", p["c"]),
                    "close": p["c"],
                    "volume": p.get("v", 0)
                })
            return candles
        except Exception as e:
            logger.error(f"❌ Error GOLD candles: {e}")
            return None

    try:
        resp = requests.get("https://api.binance.com/api/v3/klines", 
                           params={"symbol": "BTCUSDT", "interval": interval, "limit": limit}, 
                           timeout=10)
        data = resp.json()
        candles = []
        for k in data:
            candles.append({
                "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
                "close": float(k[4]), "volume": float(k[5])
            })
        return candles
    except Exception as e:
        logger.error(f"❌ Error BTC candles: {e}")
        return None

# ============================================
# INDICATORS & ANALYSIS
# ============================================
def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    if len(prices) < period + 1: return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)

def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    if len(prices) < period: return None
    mult = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = (p - ema) * mult + ema
    return round(ema, 2)

def calculate_macd(prices: List[float]) -> Tuple[Optional[float], Optional[float]]:
    e12, e26 = calculate_ema(prices, 12), calculate_ema(prices, 26)
    if e12 is None or e26 is None: return None, None
    return round(e12 - e26, 2), e12

def calculate_bollinger_bands(prices: List[float], period: int = 20) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if len(prices) < period: return None, None, None
    sma = sum(prices[-period:]) / period
    std = math.sqrt(sum((x - sma) ** 2 for x in prices[-period:]) / period)
    return round(sma, 2), round(sma + 2 * std, 2), round(sma - 2 * std, 2)

def calculate_atr(candles: List[dict], period: int = 14) -> Optional[float]:
    if len(candles) < period + 1: return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return round(sum(trs[-period:]) / period, 2)

def analyze_market_strategies(asset_name: str) -> Tuple[str, str]:
    candles = get_binance_candles(asset_name, "1h", 50)
    if not candles: return "WAIT", "Data tidak ada"
    price = candles[-1]["close"]
    prices = [c["close"] for c in candles]
    
    rsi = calculate_rsi(prices)
    macd, _ = calculate_macd(prices)
    _, upper, lower = calculate_bollinger_bands(prices)
    
    if rsi and rsi < 30 and macd and macd > 0:
        return "BUY", f"RSI Oversold ({rsi}) + MACD Positif"
    if rsi and rsi > 70 and macd and macd < 0:
        return "SELL", f"RSI Overbought ({rsi}) + MACD Negatif"
    if lower and price < lower and rsi and rsi < 40:
        return "BUY", f"Bollinger Lower ({lower:.2f}) + RSI Rendah"
    if upper and price > upper and rsi and rsi > 60:
        return "SELL", f"Bollinger Upper ({upper:.2f}) + RSI Tinggi"
    return "WAIT", "Tiada setup kuat"

def generate_ultimate_signal(asset_name: str, price: float) -> str:
    sig, reason = analyze_market_strategies(asset_name)
    icon = "🟢" if sig == "BUY" else "🔴" if sig == "SELL" else "⚪"
    return f"⚡ *SIGNAL {asset_name}*\n\n💵 ${price:,.2f}\n\n{icon} *{sig}*\n💡 {reason}\n\n⚠️ Gunakan pengurusan modal!"
