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
    logger.error("❌ DATABASE_URL kosong!")
else:
    logger.info("✅ Database URL dijumpai!")

def get_db_connection():
    if not DB_URL or DB_URL.strip() == "":
        logger.error("❌ Tiada DATABASE_URL!")
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        logger.info("✅ Sambung PostgreSQL berjaya!")
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
        logger.info("✅ Table subscribers siap!")
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
        cur.execute(
            "DELETE FROM subscribers WHERE chat_id = %s",
            (chat_id,)
        )
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
            logger.error(f"❌ Ralat GOLD candles: {e}")
            return None

    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": interval, "limit": limit},
            timeout=10
        )
        data = resp.json()
        candles = []
        for k in data:
            candles.append({
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        return candles
    except Exception as e:
        logger.error(f"❌ Ralat Binance: {e}")
        return None

# INDICATORS
def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    return round(result, 2)

def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return round(ema, 2)

def calculate_macd(prices: List[float]) -> Tuple[Optional[float], Optional[float]]:
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    if ema12 is None or ema26 is None:
        return None, None
    macd = round(ema12 - ema26, 2)
    return macd, ema12

def calculate_bollinger_bands(prices: List[float], period: int = 20) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if len(prices) < period:
        return None, None, None
    sma = sum(prices[-period:]) / period
    variance = sum((x - sma) ** 2 for x in prices[-period:]) / period
    std = math.sqrt(variance)
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    return round(sma, 2), round(upper, 2), round(lower, 2)

def calculate_atr(candles: List[dict], period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    tr_list = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return round(sum(tr_list[-period:]) / period, 2)

# ANALISIS UTAMA
def analyze_market_strategies(asset_name: str) -> Tuple[str, str]:
    candles = get_binance_candles(asset_name, "1h", 50)
    if not candles:
        return "WAIT", "Data tidak tersedia"

    price = candles[-1]["close"]
    prices = [c["close"] for c in candles]

    rsi = calculate_rsi(prices, 14)
    macd, _ = calculate_macd(prices)
    _, upper, lower = calculate_bollinger_bands(prices, 20)

    signal = "WAIT"
    reason = "Tiada setup yang kuat."

    if rsi is not None and macd is not None:
        if rsi < 30 and macd > 0:
            signal = "BUY"
            reason = f"RSI Oversold ({rsi}) + MACD Positif ({macd})"
        elif rsi > 70 and macd < 0:
            signal = "SELL"
            reason = f"RSI Overbought ({rsi}) + MACD Negatif ({macd})"
        elif lower is not None and price < lower and rsi < 40:
            signal = "BUY"
            reason = f"Bollinger Lower ({lower:.2f}) + RSI Rendah ({rsi})"
        elif upper is not None and price > upper and rsi > 60:
            signal = "SELL"
            reason = f"Bollinger Upper ({upper:.2f}) + RSI Tinggi ({rsi})"

    return signal, reason

def generate_ultimate_signal(asset_name: str, price: float) -> str:
    signal_type, reason = analyze_market_strategies(asset_name)
    emoji = "🟢" if signal_type == "BUY" else "🔴" if signal_type == "SELL" else "⚪"
    msg = (
        f"⚡ *SIGNAL ULTIMATE: {asset_name}*\n\n"
        f"💵 Harga: ${price:,.2f}\n\n"
        f"{emoji} *SIGNAL:* {signal_type}\n"
        f"💡 *Analisis:* {reason}\n\n"
        f"⚠️ Jangan entry buta. Gunakan pengurusan modal!"
    )
    return msg
