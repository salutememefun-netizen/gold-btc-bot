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

# ─────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────

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

# ─────────────────────────────────────────
# HARGA LIVE
# ─────────────────────────────────────────

def get_btc_price() -> Optional[float]:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()["bitcoin"]["usd"]
    except Exception as e:
        logger.error(f"Ralat BTC: {e}")
        return None

def get_gold_price() -> Optional[float]:
    url = "https://xaus.com/api/v1/spot"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()["spot_usd_oz"]
    except Exception as e:
        logger.error(f"Ralat GOLD: {e}")
        return None

# ─────────────────────────────────────────
# DATA DARI BINANCE
# ─────────────────────────────────────────

def get_binance_candles(symbol: str, interval: str = "1h", limit: int = 200) -> Optional[List[Dict]]:
    binance_symbol = "BTCUSDT" if symbol == "BTC" else "BTCUSDT"
    
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
        except Exception as e:
            logger.error(f"Ralat data Gold: {e}")
            return None

    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": binance_symbol, "interval": interval, "limit": limit}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
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
        logger.error(f"Ralat data Binance: {e}")
        return None

# ─────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────

def calculate_sma(prices: List[float], period: int) -> List[float]:
    sma = []
    for i in range(len(prices)):
        if i < period - 1:
            sma.append(None)
        else:
            avg = sum(prices[i-period+1:i+1]) / period
            sma.append(avg)
    return sma

def calculate_ema(prices: List[float], period: int) -> List[float]:
    if len(prices) < period:
        return [None] * len(prices)
    ema = []
    multiplier = 2 / (period + 1)
    sma = sum(prices[:period]) / period
    ema.append(sma)
    for i in range(period, len(prices)):
        ema_val = (prices[i] - ema[-1]) * multiplier + ema[-1]
        ema.append(ema_val)
    return [None] * (period - 1) + ema

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    if len(prices) < period + 1:
        return [None] * len(prices)
    rsi = []
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gains = []
    avg_losses = []
    for i in range(len(gains)):
        if i < period - 1:
            avg_gains.append(None)
            avg_losses.append(None)
        else:
            avg_g = sum(gains[i-period+1:i+1]) / period
            avg_l = sum(losses[i-period+1:i+1]) / period
            avg_gains.append(avg_g)
            avg_losses.append(avg_l)
    for i in range(len(gains)):
        if avg_gains[i] is None or avg_losses[i] is None or avg_losses[i] == 0:
            rsi.append(None)
        else:
            rs = avg_gains[i] / avg_losses[i]
            rsi_val = 100 - (100 / (1 + rs))
            rsi.append(rsi_val)
    return [None] + rsi

def calculate_macd(prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    macd_line = []
    for i in range(len(prices)):
        if ema12[i] is None or ema26[i] is None:
            macd_line.append(None)
        else:
            macd = ema12[i] - ema26[i]
            macd_line.append(macd)
    valid_macd = [m for m in macd_line if m is not None]
    signal_ema = calculate_ema(valid_macd, 9) if valid_macd else []
    signal_full = [None] * (len(prices) - len(signal_ema)) + signal_ema
    return macd_line, signal_full, None

def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Tuple[List[float], List[float], List[float]]:
    sma = calculate_sma(prices, period)
    upper = []
    lower = []
    for i in range(len(prices)):
        if sma[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = prices[i-period+1:i+1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            upper.append(sma[i] + (std_dev * std))
            lower.append(sma[i] - (std_dev * std))
    return sma, upper, lower

def calculate_atr(candles: List[dict], period: int = 14) -> List[float]:
    if len(candles) < 2:
        return [None] * len(candles)
    tr_list = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    atr = calculate_sma(tr_list, period)
    return [None] + atr

def calculate_supertrend(candles: List[dict], period: int = 10, multiplier: float = 3.0) -> Tuple[List[float], List[str]]:
    if len(candles) < period:
        return [None] * len(candles), ["NEUTRAL"] * len(candles)
    high = [c["high"] for c in candles]
    low = [c["low"] for c in candles]
    close = [c["close"] for c in candles]
    atr = calculate_atr(candles, period)
    supertrend = []
    trend = "NEUTRAL"
    for i in range(len(candles)):
        if atr[i] is None:
            supertrend.append(None)
            continue
        basis = (high[i] + low[i]) / 2
        upper = basis + (multiplier * atr[i])
        lower = basis - (multiplier * atr[i])
        if i == 0:
            supertrend.append(upper)
            trend = "NEUTRAL"
        else:
            prev_sup = supertrend[-1]
            if close[i] < prev_sup:
                supertrend.append(upper)
                trend = "BEARISH"
            elif close[i] > prev_sup:
                supertrend.append(lower)
                trend = "BULLISH"
            else:
                supertrend.append(prev_sup)
    return supertrend, [trend] * len(candles)

def detect_fvg_and_bos(candles: List[dict]) -> Dict:
    fvg_list = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if c3["low"] > c1["high"]:
            fvg_list.append({"type": "BULLISH", "top": c1["high"], "bottom": c3["low"]})
        elif c3["high"] < c1["low"]:
            fvg_list.append({"type": "BEARISH", "top": c3["high"], "bottom": c1["low"]})
    if len(candles) < 5:
        bos = "NEUTRAL"
    else:
        highs = [c["high"] for c in candles[-5:]]
        lows = [c["low"] for c in candles[-5:]]
        if highs[-1] > highs[-3] and lows[-1] > lows[-3]:
            bos = "BULLISH_BOS"
        elif highs[-1] < highs[-3] and lows[-1] < lows[-3]:
            bos = "BEARISH_BOS"
        else:
            bos = "NEUTRAL"
    return {"fvg": fvg_list, "bos": bos}

# ─────────────────────────────────────────
# SIGNAL UTAMA
# ─────────────────────────────────────────

def analyze_market_strategies(asset_name: str) -> Tuple[str, str, str]:
    candles = get_binance_candles(asset_name, "1h", 50)
    if not candles:
        return "WAIT", "Data tidak mencukupi", "N/A"
    price = candles[-1]["close"]
    prices = [c["close"] for c in candles]
    rsi = calculate_rsi(prices, 14)
    macd_line, signal_line, _ = calculate_macd(prices)
    sma, upper, lower = calculate_bollinger_bands(prices, 20, 2)
    atr = calculate_atr(candles, 
