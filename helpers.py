#!/usr/bin/env python3
"""
Helper functions - Auto detect SEMUA kemungkinan nama variable
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
# DATABASE: Cuba SEMUA nama yang mungkin
# ============================================
DB_URL = (
    os.getenv("DATABASE_URL") or
    os.getenv("POSTGRES_URL") or
    os.getenv("POSTGRES_CONNECTION_STRING") or
    os.getenv("DATABASE") or
    os.getenv("DB_URL") or
    os.getenv("POSTGRES_HOST") or
    os.getenv("RAILWAY_POSTGRES_URL") or
    ""
)

if not DB_URL:
    logger.error("❌ TIDAK ADA DATABASE URL! Cuba semua nama:")
    for key in os.environ:
        if 'DB' in key.upper() or 'POSTGRES' in key.upper() or 'DATABASE' in key.upper():
            val = os.getenv(key)
            logger.error(f"   {key} = {val[:20]}...")
else:
    logger.info(f"✅ Guna database dari: {[k for k in os.environ if os.getenv(k) == DB_URL][0]}")

def get_db_connection():
    if not DB_URL:
        logger.error("❌ Tiada DATABASE_URL untuk sambung!")
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        logger.info("✅ Berhasil sambung PostgreSQL!")
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
        logger.info("✅ Table 'subscribers' siap.")
        return True
    except Exception as e:
        logger.error(f"❌ Error init DB: {e}")
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
        subs = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return subs
    except Exception as e:
        logger.error(f"❌ Error get subscribers: {e}")
        return []

# ============================================
# API: Harga Live
# ============================================
def get_btc_price() -> Optional[float]:
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/simple/price", 
                           params={"ids": "bitcoin", "vs_currencies": "usd"}, timeout=5)
        return resp.json()["bitcoin"]["usd"]
    except Exception as e:
        logger.error(f"❌ Error BTC: {e}")
        return None

def get_gold_price() -> Optional[float]:
    try:
        resp = requests.get("https://xaus.com/api/v1/spot", timeout=5)
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
# INDICATORS
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
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2
