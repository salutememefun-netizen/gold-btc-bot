#!/usr/bin/env python3
"""
Helper functions untuk Bot Trading GOLD/BTC
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

# DATABASE CONFIG
DB_URL = (
    os.getenv("DATABASE_URL") or
    os.getenv("POSTGRES_URL") or
    os.getenv("DATABASE") or
    os.getenv("DB_URL") or
    ""
)

if not DB_URL or DB_URL.strip() == "":
    logger.error("❌ DATABASE_URL kosong atau tidak dijumpai!")
else:
    logger.info("✅ Database URL dijumpai!")

def get_db_connection():
    if not DB_URL or DB_URL.strip() == "":
        logger.error("❌ Tiada DATABASE_URL untuk sambung!")
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        logger.info("✅ Berhasil sambung PostgreSQL!")
        return conn
    except Exception as e:
        logger.error(f"❌ Ralat DB: {e}")
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
        logger.error(f"❌ Ralat init DB: {e}")
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
        logger.error(f"❌ Ralat add subscriber: {e}")
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
        logger.error(f"❌ Ralat remove subscriber: {e}")
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
        logger.error(f"❌ Ralat get subscribers: {e}")
        return []

# HARGA LIVE
def get_btc_price() -> Optional[float]:
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "usd"}
        response = requests.get(url, params=params, timeout=5)
        return response.json()["bitcoin"]["usd"]
    except Exception as e:
        logger.error(f"❌ Ralat BTC: {e}")
        return None

def get_gold_price() -> Optional[float]:
    try:
        url = "https://xaus.com/api/v1/spot"
        response = requests.get(url, timeout=5)
        return response.json()["spot_usd_oz"]
    except Exception as e:
        logger.error(f"❌ Ralat GOLD: {e}")
        return None

# DATA CANDLES
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
            logger.error(f"❌
