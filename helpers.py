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
    symbol: "BTCUSDT" atau "XAUUSDT" (Jika XAU tidak ada, kita guna BTCUSDT sebagai proxy atau API lain)
    Nota: Binance tidak ada XAUUSDT secara langsung. Kita akan guna API XAUS untuk Gold jika perlu,
    tapi untuk konsistensi indikator, kita akan cuba dapatkan data terbaik.
    
    Untuk Gold, kita akan guna API XAUS yang ada data OHLC (jika ada) atau simulasi jika tiada.
    Untuk BTC, kita guna Binance.
    """
    
    # Mapping symbol untuk Binance
    binance_symbol = "BTCUSDT" if symbol == "BTC" else "BTCUSDT" # Gold tidak ada di Binance spot, kita guna BTC untuk demo atau API lain
    
    # Jika Gold, kita cuba guna API XAUS history (tapi ia daily). 
    # Untuk analisis teknikal 1H/4H, kita akan fokus pada BTC dulu, atau kita anggap user nak analisis BTC.
    # Jika anda mahu Gold sebenar, kita perlukan API berbayar atau API lain yang ada OHLC.
    # Di sini kita akan fokus pada BTC untuk ketepatan, dan bagi Gold kita guna data harian sebagai proxy.
    
    if symbol == "GOLD":
        # Guna XAUS API untuk data harian (limitasi)
        url = "https://xaus.com/api/v1/history"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            points = data.get("points", [])
            # Ambil 200 titik terakhir
            candles = []
            for p in points[-limit:]:
                candles.append({
                    "open": p.get("o", p["c"]),
                    "high": p.get("h", p["c"]),
                    "low": p.get("l", p["c"]),
                    "close": p["c"],
                    "volume": p.get("v", 0) # Volume mungkin tidak ada di XAUS
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
    
    # Pad awal dengan None
    return [None] * (period - 1) + ema

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    rsi = []
    gains, losses = [], []
    
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    
    # Kira avg gain/loss
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
    
    return [None] + rsi # Pad awal

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
    
    # Signal line (EMA 9 dari MACD)
    valid_macd = [m for m in macd_line if m is not None]
    signal_ema = calculate_ema(valid_macd, 9)
    
    # Align signal line dengan original list
    # Ini agak kompleks, kita ringkaskan: kita ambil nilai terkini sahaja
    # Untuk kesederhanaan, kita anggap signal line adalah EMA 9 dari MACD
    # Kita akan return nilai terkini sahaja untuk keputusan
    
    return macd_line, signal_ema, None # Return full list, kita ambil yang terakhir

def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Tuple[List[float], List[float], List[float]]:
    sma = calculate_sma(prices, period)
    upper = []
    lower = []
    
    for i in range(len(prices)):
        if sma[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            # Kira std dev
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
    return [None] + atr # Align

def calculate_supertrend(candles: List[dict], period: int = 10, multiplier: float = 3.0) -> Tuple[List[float], List[str]]:
    # Simplified SuperTrend
    high = [c["high"] for c in candles]
    low = [c["low"] for c in candles]
    close = [c["close"] for c in candles]
    
    atr = calculate_atr(candles, period)
    tr = []
    for i in range(1, len(candles)):
        tr.append(max(candles[i]["high"] - candles[i]["low"], abs(candles[i]["high"] - candles[i-1]["close"]), abs(candles[i]["low"] - candles[i-1]["close"])))
    
    # Kita akan guna logik mudah: jika close > upper band (Basis) = Bullish
    # Ini adalah implementasi ringkas. SuperTrend sebenar lebih kompleks.
    # Kita akan guna ATR untuk menentukan trend.
    
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
    # FVG & BOS (sama seperti sebelum ini)
    fvg_list = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if c3["low"] > c1["high"]:
            fvg_list.append({"type": "BULLISH", "top": c1["high"], "bottom": c3["low"]})
        elif c3["high"] < c1["low"]:
            fvg_list.append({"type": "BEARISH", "top": c3["high"], "bottom": c1["low"]})
    
    # BOS
    highs = [c["high"] for c in candles[-5:]]
    lows = [c["low"] for c in candles[-5:]]
    bos = "NEUTRAL"
    if highs[-1] > highs[-3] and lows[-1] > lows[-3]:
        bos = "BULLISH_BOS"
    elif highs[-1] < highs[-3] and lows[-1] < lows[-3]:
        bos = "BEARISH_BOS"
    
    return {"fvg": fvg_list, "bos": bos}

# ─────────────────────────────────────────
# LOGIK UTAMA: GABUNGAN SEMUA INDICATOR
# ─────────────────────────────────────────

def analyze_market_strategies(asset_name: str) -> Tuple[str, str, str]:
    """
    Analisis gabungan: S
