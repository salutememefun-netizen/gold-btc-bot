import requests
import logging
import math
import psycopg2
import os
from typing import Optional, List, Tuple, Dict
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# DATABASE
DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if not DB_URL:
        return None
    try:
        return psycopg2.connect(DB_URL)
    except Exception as e:
        logger.error(f"Ralat DB: {e}")
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
        return True
    except Exception as e:
        logger.error(f"Ralat init DB: {e}")
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
        logger.error(f"Ralat add subscriber: {e}")
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
        logger.error(f"Ralat remove subscriber: {e}")
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
        logger.error(f"Ralat get subscribers: {e}")
        return []

# HARGA LIVE
def get_btc_price() -> Optional[float]:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}
    try:
        response = requests.get(url, params=params, timeout=5)
        return response.json()["bitcoin"]["usd"]
    except Exception as e:
        logger.error(f"Ralat BTC: {e}")
        return None

def get_gold_price() -> Optional[float]:
    url = "https://xaus.com/api/v1/spot"
    try:
        response = requests.get(url, timeout=5)
        return response.json()["spot_usd_oz"]
    except Exception as e:
        logger.error(f"Ralat GOLD: {e}")
        return None

# DATA BINANCE
def get_binance_candles(symbol: str, interval: str = "1h", limit: int = 100) -> Optional[List[Dict]]:
    if symbol == "GOLD":
        url = "https://xaus.com/api/v1/history"
        try:
            resp = requests.get(url, timeout=10)
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
        except:
            return None

    symbol = "BTCUSDT"
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
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
        logger.error(f"Ralat Binance: {e}")
        return None

# INDICATORS
def calculate_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calculate_ema(prices: List[float], period: int) -> float:
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return round(ema, 2)

def calculate_macd(prices: List[float]) -> Tuple[float, float]:
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    if ema12 is None or ema26 is None:
        return None, None
    macd = ema12 - ema26
    return round(macd, 2), round(ema12, 2)

def calculate_bollinger_bands(prices: List[float], period: int = 20) -> Tuple[float, float, float]:
    if len(prices) < period:
        return None, None, None
    sma = sum(prices[-period:]) / period
    variance = sum((x - sma) ** 2 for x in prices[-period:]) / period
    std = math.sqrt(variance)
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    return round(sma, 2), round(upper, 2), round(lower, 2)

def calculate_atr(candles: List[dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return None
    tr_list = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    atr = sum(tr_list[-period:]) / period
    return round(atr, 2)

# ANALISIS UTAMA
def analyze_market_strategies(asset_name: str) -> Tuple[str, str]:
    candles = get_binance_candles(asset_name, "1h", 50)
    if not candles:
        return "WAIT", "Data tidak tersedia"
    
    price = candles[-1]["close"]
    prices = [c["close"] for c in candles]
    
    # Kira indikator
    rsi = calculate_rsi(prices, 14)
    macd, ema12 = calculate_macd(prices)
    sma, upper, lower = calculate_bollinger_bands(prices, 20)
    atr = calculate_atr(candles, 14)
    
    signal = "WAIT"
    reason = "Tiada setup yang kuat."
    
    # Logik BUY
    if rsi and rsi < 30 and macd and macd > 0:
        signal = "BUY"
        reason = f"RSI Oversold ({rsi}) + MACD Positif ({macd})"
    
    # Logik SELL
    elif rsi and rsi > 70 and macd and macd < 0:
        signal = "SELL"
        reason = f"RSI Overbought ({rsi}) + MACD Negatif ({macd})"
    
    # Bollinger Bands
    elif price and lower and price < lower and rsi and rsi < 40:
        signal = "BUY"
        reason = f"Harga sentuh Bollinger Lower ({lower:.2f}) + RSI Rendah ({rsi})"
    
    elif price and upper and price > upper and rsi and rsi > 60:
        signal = "SELL"
        reason = f"Harga sentuh Bollinger Upper ({upper:.2f}) + RSI Tinggi ({rsi})"
    
    return signal, reason

def generate_ultimate_signal(asset_name: str, price: float) -> str:
    signal_type, reason = analyze_market_strategies(asset_name)
    
    fmt = lambda x: f"${x:,.2f}" if isinstance(x, float) else x
    
    msg = (
        f"⚡ *SIGNAL ULTIMATE: {asset_name}*\n\n"
        f"💵 Harga: {fmt(price)}\n\n"
        f"🚀 *SIGNAL:* {signal_type}\n"
        f"💡 *Analisis:* {reason}\n\n"
        f"⚠️ Jangan entry buta. Gunakan pengurusan modal!"
    )
    return msg

# ALIAS
gold_market_operators = generate_ultimate_signal
