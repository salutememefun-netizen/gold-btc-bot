import requests
import logging
from typing import Optional, Tuple, List

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# HARGA LIVE
# ─────────────────────────────────────────

def get_btc_price() -> Optional[float]:
    """Ambil harga BTC dari CoinGecko."""
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
    """Ambil harga GOLD dari XAUS."""
    url = "https://xaus.com/api/v1/spot"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()["spot_usd_oz"]
    except Exception as e:
        logger.error(f"Ralat GOLD: {e}")
        return None


# ─────────────────────────────────────────
# FEAR & GREED INDEX
# ─────────────────────────────────────────

def get_fear_greed() -> Tuple[Optional[int], Optional[str]]:
    """Ambil Fear & Greed Index dari alternative.me (percuma)."""
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["data"][0]
        value = int(data["value"])
        classification = data["value_classification"]
        return value, classification
    except Exception as e:
        logger.error(f"Ralat Fear & Greed: {e}")
        return None, None


# ─────────────────────────────────────────
# DATA HISTORIS UNTUK RSI & EMA
# ─────────────────────────────────────────

def get_btc_historical(days: int = 30) -> Optional[List[float]]:
    """Ambil data harga historis BTC dari CoinGecko."""
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        prices = [p[1] for p in response.json()["prices"]]
        return prices
    except Exception as e:
        logger.error(f"Ralat historis BTC: {e}")
        return None

def get_gold_historical(days: int = 30) -> Optional[List[float]]:
    """Ambil data historis GOLD dari XAUS."""
    url = "https://xaus.com/api/v1/history"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        points = data.get("points", [])
        # Ambil 'days' hari terakhir
        prices = [p["c"] for p in points[-days:]]
        return prices
    except Exception as e:
        logger.error(f"Ralat historis GOLD: {e}")
        return None


# ─────────────────────────────────────────
# PENGIRAAN TEKNIKAL
# ─────────────────────────────────────────

def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Kira RSI (Relative Strength Index).
    RSI > 70 = Overbought (terlalu mahal, kemungkinan turun)
    RSI < 30 = Oversold (terlalu murah, kemungkinan naik)
    """
    if not prices or len(prices) < period + 1:
        return None

    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """
    Kira EMA (Exponential Moving Average).
    """
    if not prices or len(prices) < period:
        return None

    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period  # SMA sebagai nilai awal

    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return round(ema, 2)

def get_ema_signal(prices: List[float]) -> Tuple[Optional[float], Optional[float], str]:
    """
    EMA 9 vs EMA 21 Crossover Signal.
    EMA9 > EMA21 = BUY Signal (Golden Cross)
    EMA9 < EMA21 = SELL Signal (Death Cross)
    """
    ema9 = calculate_ema(prices, 9)
    ema21 = calculate_ema(prices, 21)

    if ema9 is None or ema21 is None:
        return ema9, ema21, "⚪ Data Tidak Cukup"

    if ema9 > ema21:
        signal = "🟢 BUY (Golden Cross: EMA9 > EMA21)"
    elif ema9 < ema21:
        signal = "🔴 SELL (Death Cross: EMA9 < EMA21)"
    else:
        signal = "⚪ NEUTRAL (EMA9 = EMA21)"

    return ema9, ema21, signal

def interpret_rsi(rsi: float) -> str:
    """Tafsiran RSI dalam bahasa mudah."""
    if rsi >= 70:
        return f"🔴 Overbought ({rsi}) — Harga terlalu tinggi, kemungkinan turun"
    elif rsi <= 30:
        return f"🟢 Oversold ({rsi}) — Harga terlalu rendah, kemungkinan naik"
    elif rsi >= 55:
        return f"🟡 Sedikit Bullish ({rsi}) — Momentum positif"
    elif rsi <= 45:
        return f"🟠 Sedikit Bearish ({rsi}) — Momentum negatif"
    else:
        return f"⚪ Neutral ({rsi}) — Pasaran dalam keseimbangan"

def interpret_fear_greed(value: int) -> str:
    """Emoji berdasarkan nilai Fear & Greed."""
    if value >= 75:
        return "🤑 Extreme Greed"
    elif value >= 55:
        return "😊 Greed"
    elif value >= 45:
        return "😐 Neutral"
    elif value >= 25:
        return "😨 Fear"
    else:
        return "😱 Extreme Fear"


# ─────────────────────────────────────────
# SMART ZONES (DIKEMASKINI)
# ─────────────────────────────────────────

def calculate_smart_zones(
    price: float, asset: str
) -> Tuple[float, float, float, float, str, str]:
    """Kira zon entry berdasarkan volatiliti dan trend."""
    if asset == "BTC":
        volatility = 0.025
        threshold_buy = 60000
        threshold_sell = 65000
    else:
        volatility = 0.015
        threshold_buy = 2000
        threshold_sell = 2400

    if price > threshold_sell:
        trend = "BULLISH 🟢"
        buy_margin = price * volatility
        sell_margin = price * (volatility * 0.5)
        buy_low = price - buy_margin
        buy_high = price - (buy_margin * 0.5)
        sell_low = price + sell_margin
        sell_high = price + (sell_margin * 1.5)
        advice = "Trend Naik: Cari Buy pada dip."
    elif price < threshold_buy:
        trend = "BEARISH 🔴"
        sell_margin = price * volatility
        buy_margin = price * (volatility * 0.5)
        sell_low = price + sell_margin
        sell_high = price + (sell_margin * 0.5)
        buy_low = price - buy_margin
        buy_high = price - (buy_margin * 1.5)
        advice = "Trend Turun: Cari Sell pada rally."
    else:
        trend = "NEUTRAL ⚪"
        margin = price * (volatility * 0.8)
        buy_low = price - margin
        buy_high = price - (margin * 0.5)
        sell_low = price + (margin * 0.5)
        sell_high = price + margin
        advice = "Sideways: Entry berhati-hati di zon sempadan."

    return buy_low, buy_high, sell_low, sell_high, trend, advice


# ─────────────────────────────────────────
# SIGNAL GENERATOR
# ─────────────────────────────────────────

def generate_smart_signal(asset_name: str, price: float) -> str:
    """
    Bina signal lengkap dengan RSI + EMA + Fear & Greed + Smart Zones.
    """
    if not price:
        return f"❌ Data {asset_name} tidak tersedia."

    fmt = lambda x: f"${x:,.2f}"

    # Ambil data historis
    if asset_name == "BTC":
        prices_hist = get_btc_historical(30)
    else:
        prices_hist = get_gold_historical(30)

    # Kira RSI
    rsi = calculate_rsi(prices_hist) if prices_hist else None
    rsi_text = interpret_rsi(rsi) if rsi else "⚪ RSI tidak tersedia"

    # Kira EMA
    ema9, ema21, ema_signal = get_ema_signal(prices_hist) if prices_hist else (None, None, "⚪ EMA tidak tersedia")
    ema_text = (
        f"EMA9: {fmt(ema9)} | EMA21: {fmt(ema21)}\n"
        f"   Signal: {ema_signal}"
    ) if ema9 and ema21 else "⚪ EMA tidak tersedia"

    # Fear & Greed (hanya untuk BTC)
    fg_text = ""
    if asset_name == "BTC":
        fg_value, fg_class = get_fear_greed()
        if fg_value:
            fg_emoji = interpret_fear_greed(fg_value)
            fg_text = f"\n😱 *Fear & Greed:* {fg_value}/100 — {fg_emoji}\n"

    # Smart Zones
    buy_low, buy_high, sell_low, sell_high, trend, advice = calculate_smart_zones(price, asset_name)

    msg = (
        f"📊 *SMART SIGNAL: {asset_name}*\n"
        f"💵 Harga: {fmt(price)}\n"
        f"📈 Trend: {trend}\n"
        f"💡 {advice}\n"
        f"{fg_text}\n"
        f"📉 *RSI (14):*\n"
        f"   {rsi_text}\n\n"
        f"📊 *EMA Crossover:*\n"
        f"   {ema_text}\n\n"
        f"🟢 *ZON BUY (LONG)*\n"
        f"   Entry: {fmt(buy_low)} — {fmt(buy_high)}\n"
        f"   Stop Loss: {fmt(buy_low * 0.995)}\n"
        f"   Take Profit: {fmt(buy_high * 1.04)}\n\n"
        f"🔴 *ZON SELL (SHORT)*\n"
        f"   Entry: {fmt(sell_low)} — {fmt(sell_high)}\n"
        f"   Stop Loss: {fmt(sell_high * 1.005)}\n"
        f"   Take Profit: {fmt(sell_low * 0.96)}\n\n"
        f"⚠️ *Amaran:* Gunakan pengurusan modal. "
        f"Analisis automatik sahaja."
    )
    return msg

def analyze_gold_btc() -> str:
    """Laporan penuh BTC + GOLD."""
    btc = get_btc_price()
    gold = get_gold_price()

    separator = "\n" + ("─" * 30) + "\n\n"
    return (
        f"📈 *Laporan Pasaran PRO*\n\n"
        + generate_smart_signal("BTC", btc)
        + separator
        + generate_smart_signal("GOLD", gold)
    )

# Alias
gold_market_operators = analyze_gold_btc
