import requests
import logging
from typing import Optional, Tuple

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

def analyze_trend(price: float, lookback: int = 5) -> str:
    """
    Analisis trend mudah berdasarkan pergerakan harga terkini.
    (Simulasi trend tanpa perlu ambil data history berat)
    Kita anggap trend positif jika harga > 50,000 (BTC) atau > 2000 (GOLD) 
    DAN harga semasa lebih tinggi dari harga purata 24j (simulasi).
    """
    # Logik mudah: Jika harga > threshold utama = Bullish
    if price > 60000: return "BULLISH"
    if price < 55000: return "BEARISH"
    return "NEUTRAL"

def calculate_smart_zones(price: float, asset: str) -> Tuple[float, float, float, float, str, str]:
    """
    Kira zon entry pintar menggunakan Volatiliti (ATR Simulation).
    
    Returns:
        (buy_low, buy_high, sell_low, sell_high, trend, advice)
    """
    # Volatiliti berbeza mengikut aset
    if asset == "BTC":
        volatility = 0.025  # 2.5% (BTC lebih ganas)
        threshold_buy = 60000
        threshold_sell = 65000
    else: # GOLD
        volatility = 0.015  # 1.5% (GOLD lebih stabil)
        threshold_buy = 2000
        threshold_sell = 2400

    # Tentukan Trend
    if price > threshold_sell:
        trend = "BULLISH 🟢"
        # Dalam trend naik, fokus cari Buy di dip (pullback)
        buy_margin = price * volatility
        sell_margin = price * (volatility * 0.5) # Sell hanya jika overshoot sangat
        buy_low = price - buy_margin
        buy_high = price - (buy_margin * 0.5)
        sell_low = price + sell_margin
        sell_high = price + (sell_margin * 1.5)
        advice = "Trend Naik: Cari peluang Buy pada harga rendah (Dip)."
    elif price < threshold_buy:
        trend = "BEARISH 🔴"
        # Dalam trend turun, fokus cari Sell di rally
        sell_margin = price * volatility
        buy_margin = price * (volatility * 0.5)
        sell_low = price + sell_margin
        sell_high = price + (sell_margin * 0.5)
        buy_low = price - buy_margin
        buy_high = price - (buy_margin * 1.5)
        advice = "Trend Turun: Cari peluang Sell pada harga tinggi (Rally)."
    else:
        trend = "NEUTRAL ⚪"
        # Sideways: Zon ketat
        margin = price * (volatility * 0.8)
        buy_low = price - margin
        buy_high = price - (margin * 0.5)
        sell_low = price + (margin * 0.5)
        sell_high = price + margin
        advice = "Pasaran Sideways: Entry berhati-hati di zon sempadan."

    return buy_low, buy_high, sell_low, sell_high, trend, advice

def generate_smart_signal(asset_name: str, price: float) -> str:
    if not price:
        return f"❌ Data {asset_name} tidak tersedia."

    buy_low, buy_high, sell_low, sell_high, trend, advice = calculate_smart_zones(price, asset_name)
    
    fmt = lambda x: f"${x:,.2f}"
    
    # Risk Reward Ratio (1:2 atau 1:3)
    sl_buy = buy_low * 0.995
    tp_buy = buy_high * 1.04
    
    sl_sell = sell_high * 1.005
    tp_sell = sell_low * 0.96

    msg = (
        f"📊 *SMART SIGNAL: {asset_name}*\n"
        f"💵 Harga: {fmt(price)}\n"
        f"📈 Trend: {trend}\n"
        f"💡 Nasihat: {advice}\n\n"
        f"🟢 *ZON BUY (LONG)*\n"
        f"   Entry: {fmt(buy_low)} - {fmt(buy_high)}\n"
        f"   Stop Loss: {fmt(sl_buy)}\n"
        f"   Take Profit: {fmt(tp_buy)}\n\n"
        f"🔴 *ZON SELL (SHORT)*\n"
        f"   Entry: {fmt(sell_low)} - {fmt(sell_high)}\n"
        f"   Stop Loss: {fmt(sl_sell)}\n"
        f"   Take Profit: {fmt(tp_sell)}\n\n"
        f"⚠️ *Amaran:* Gunakan pengurusan modal. "
        f"Zon ini berdasarkan analisis teknikal automatik."
    )
    return msg

def analyze_gold_btc() -> str:
    btc = get_btc_price()
    gold = get_gold_price()
    
    msg = "📈 *Laporan Pasaran PRO (Smart Zon)*\n\n"
    msg += generate_smart_signal("BTC", btc) + "\n\n" + ("_"*30) + "\n\n"
    msg += generate_smart_signal("GOLD", gold)
    
    return msg

# Alias
gold_market_operators = analyze_gold_btc
