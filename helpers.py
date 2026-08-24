import requests
import logging
import math
from typing import Optional, List, Tuple, Dict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# DATA DARI BINANCE (OHLC + Volume)
# ─────────────────────────────────────────

def get_binance_candles(symbol: str, interval: str = "1h", limit: int = 200) -> Optional[List[Dict]]:
    """
    Ambil data candle dari Binance Public API.
    symbol: "BTCUSDT" atau "XAUUSDT" (Jika XAU tidak ada, kita guna BTCUSDT sebagai proxy)
    Untuk Gold, kita akan guna API XAUS jika perlu, tapi untuk konsistensi, kita fokus pada BTC.
    """
    
    # Mapping symbol untuk Binance
    binance_symbol = "BTCUSDT" if symbol == "BTC" else "BTCUSDT"
    
    if symbol == "GOLD":
        # Guna XAUS API untuk data harian (limitasi)
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

    # Untuk BTC, guna Binance
    url = f"https://api.binance.com/api/v3/klines"
    params = {
        "symbol": binance_symbol,
        "interval": interval,
        "limit": limit
    }
    
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
# PENGIRAAN INDICATORS
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
    ema = []
    multiplier = 2 / (period + 1)
    sma = sum(prices[:period]) / period
    ema.append(sma)
    
    for i in range(period, len(prices)):
        ema_val = (prices[i] - ema[-1]) * multiplier + ema[-1]
        ema.append(ema_val)
    
    return [None] * (period - 1) + ema

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
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
    signal_line = []
    
    for i in range(len(prices)):
        if ema12[i] is None or ema26[i] is None:
            macd_line.append(None)
            signal_line.append(None)
        else:
            macd = ema12[i] - ema26[i]
            macd_line.append(macd)
    
    valid_macd = [m for m in macd_line if m is not None]
    signal_ema = calculate_ema(valid_macd, 9)
    
    # Align signal line
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
    
    # BOS
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
# LOGIK UTAMA: GABUNGAN SEMUA INDICATOR
# ─────────────────────────────────────────

def analyze_market_strategies(asset_name: str) -> Tuple[str, str, str]:
    """
    Analisis gabungan: SMC, MACD, Bollinger, ATR, SuperTrend, Volume.
    Returns: (signal_type, reason, zone)
    """
    candles = get_binance_candles(asset_name, "1h", 50)
    if not candles:
        return "WAIT", "Data tidak mencukupi", "N/A"
    
    # Dapatkan harga semasa
    price = candles[-1]["close"]
    prices = [c["close"] for c in candles]
    
    # Kira indikator
    rsi = calculate_rsi(prices, 14)
    macd_line, signal_line, _ = calculate_macd(prices)
    sma, upper, lower = calculate_bollinger_bands(prices, 20, 2)
    atr = calculate_atr(candles, 14)
    supertrend, st_trend = calculate_supertrend(candles, 10, 3.0)
    smc_data = detect_fvg_and_bos(candles)
    
    # Ambil nilai terkini
    rsi_now = rsi[-1] if rsi and len(rsi) > 0 else None
    macd_now = macd_line[-1] if macd_line and len(macd_line) > 0 else None
    signal_now = signal_line[-1] if signal_line and len(signal_line) > 0 else None
    upper_now = upper[-1] if upper and len(upper) > 0 else None
    lower_now = lower[-1] if lower and len(lower) > 0 else None
    atr_now = atr[-1] if atr and len(atr) > 0 else None
    supertrend_now = supertrend[-1] if supertrend and len(supertrend) > 0 else None
    bos = smc_data["bos"]
    fvg_list = smc_data["fvg"]
    
    # Logik Signal
    signal = "WAIT"
    reason = "Tiada setup yang kuat."
    zone = "N/A"
    
    # 1. SMC + Volume Breakout
    if bos == "BULLISH_BOS" and fvg_list:
        # Cari FVG Bullish terdekat
        for fvg in reversed(fvg_list):
            if fvg["type"] == "BULLISH" and price >= fvg["bottom"] and price <= fvg["top"]:
                signal = "BUY (SMC + BOS)"
                reason = f"BOS Naik + Harga masuk FVG Bullish di {fvg['top']:.2f} - {fvg['bottom']:.2f}"
                zone = f"Buy Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}"
                break
    
    elif bos == "BEARISH_BOS" and fvg_list:
        for fvg in reversed(fvg_list):
            if fvg["type"] == "BEARISH" and price <= fvg["top"] and price >= fvg["bottom"]:
                signal = "SELL (SMC + BOS)"
                reason = f"BOS Turun + Harga masuk FVG Bearish di {fvg['top']:.2f} - {fvg['bottom']:.2f}"
                zone = f"Sell Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}"
                break
    
    # 2. MACD + Bollinger Bands
    if not signal or signal == "WAIT":
        if rsi_now and rsi_now < 30 and macd_now and signal_now and macd_now > signal_now:
            signal = "BUY (MACD + RSI)"
            reason = "RSI Oversold + MACD Bullish Crossover"
            zone = f"Buy Zone: {lower_now:.2f} - {upper_now:.2f}" if lower_now else "N/A"
        
        elif rsi_now and rsi_now > 70 and macd_now and signal_now and macd_now < signal_now:
            signal = "SELL (MACD + RSI)"
            reason = "RSI Overbought + MACD Bearish Crossover"
            zone = f"Sell Zone: {lower_now:.2f} - {upper_now:.2f}" if lower_now else "N/A"
    
    # 3. SuperTrend + ATR Filter
    if not signal or signal == "WAIT":
        if supertrend_now and price > supertrend_now and atr_now and atr_now > 100:
            signal = "BUY (SuperTrend)"
            reason = "Trend Naik (SuperTrend) + Volatiliti Tinggi (ATR)"
            zone = "N/A"
        elif supertrend_now and price < supertrend_now and atr_now and atr_now > 100:
            signal = "SELL (SuperTrend)"
            reason = "Trend Turun (SuperTrend) + Volatiliti Tinggi (ATR)"
            zone = "N/A"
    
    return signal, reason, zone

# ─────────────────────────────────────────
# FUNGSI UTAMA UNTUK BOT
# ─────────────────────────────────────────

def generate_ultimate_signal(asset_name: str, price: float) -> str:
    """
    Fungsi utama untuk bot.
    """
    signal_type, reason, zone = analyze_market_strategies(asset_name)
    
    fmt = lambda x: f"${x:,.2f}" if isinstance(x, float) else x

    msg = (
        f"⚡ *ULTIMATE SIGNAL: {asset_name}*\n\n"
        f"💵 Harga: {fmt(price)}\n"
        f"📊 Trend: {get_bos_display(get_bos_type(get_binance_candles(asset_name, '1h', 50)))}\n\n"
        f"🚀 *SIGNAL:* {signal_type}\n\n"
        f"📍 *Zon:* {zone}\n"
        f"💡 *Analisis:* {reason}\n\n"
        f"⚠️ *Amaran:* Gabungan indikator. Jangan entry buta!"
    )
    return msg

# Helper functions
def get_bos_type(candles):
    if not candles: return "NEUTRAL"
    return detect_fvg_and_bos(candles)["bos"]

def get_bos_display(bos_type):
    if bos_type == "BULLISH_BOS": return "🟢 BULLISH BOS"
    if bos_type == "BEARISH_BOS": return "🔴 BEARISH BOS"
    return "⚪ NEUTRAL"
# ─────────────────────────────────────────
# DATABASE FUNCTIONS (PostgreSQL)
# ─────────────────────────────────────────
import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Sambung ke PostgreSQL"""
    if not DB_URL:
        return None
    try:
        return psycopg2.connect(DB_URL)
    except Exception as e:
        logger.error(f"Ralat DB: {e}")
        return None

def init_db():
    """Cipta table subscribers jika belum ada"""
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
    """Tambah subscriber ke database"""
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
    """Buang subscriber dari database"""
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
    """Dapatkan semua chat_id subscriber"""
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
# HARGA LIVE (Untuk fallback)
# ─────────────────────────────────────────

def get_btc_price() -> Optional[float]:
    """Ambil harga BTC dari CoinGecko"""
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
    """Ambil harga GOLD dari XAUS"""
    url = "https://xaus.com/api/v1/spot"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()["spot_usd_oz"]
    except Exception as e:
        logger.error(f"Ralat GOLD: {e}")
        return None
# Alias
gold_market_operators = generate_ultimate_signal
