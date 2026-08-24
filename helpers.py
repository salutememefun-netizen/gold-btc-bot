import requests
import logging
from typing import Optional

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_btc_price() -> Optional[float]:
    """Ambil harga BTC dari CoinGecko API."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data["bitcoin"]["usd"]
        logger.info(f"Harga BTC: ${price:,.2f}")
        return price
    except Exception as e:
        logger.error(f"Ralat ambil harga BTC: {e}")
        return None


def get_gold_price() -> Optional[float]:
    """
    Ambil harga GOLD (XAU/USD) dari xaus.com.
    Percuma, tiada API key diperlukan.
    """
    url = "https://xaus.com/api/v1/spot"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data["spot_usd_oz"]
        logger.info(f"Harga GOLD: ${price:,.2f}")
        return price
    except Exception as e:
        logger.error(f"Ralat ambil harga GOLD: {e}")
        return None


def get_market_sentiment(btc_price: float, gold_price: float) -> str:
    """Analisis trend mudah berdasarkan harga semasa."""
    btc_trend = "🟢 Naik" if btc_price > 60000 else "🔴 Turun"
    gold_trend = "🟢 Naik" if gold_price > 2000 else "🔴 Turun"

    if btc_price > 65000 and gold_price > 2400:
        sentiment = "🚀 *Bullish* - Kedua-dua aset menunjukkan kekuatan."
    elif btc_price < 55000 and gold_price < 2000:
        sentiment = "📉 *Bearish* - Pasaran sedang lemah."
    else:
        sentiment = "⚖️ *Neutral* - Pasaran dalam keadaan tidak menentu."

    return btc_trend, gold_trend, sentiment


def analyze_gold_btc() -> str:
    """
    Fungsi utama analisis GOLD & BTC.
    Dipanggil oleh bot apabila user ketik /analyze.
    """
    btc_price = get_btc_price()
    gold_price = get_gold_price()

    # Bina baris harga
    btc_msg = f"💰 BTC: ${btc_price:,.2f}" if btc_price else "❌ Gagal ambil harga BTC"
    gold_msg = f"🏆 GOLD (XAU): ${gold_price:,.2f}" if gold_price else "❌ Gagal ambil harga GOLD"

    # Bina analisis
    if btc_price and gold_price:
        btc_trend, gold_trend, sentiment = get_market_sentiment(btc_price, gold_price)
        analysis = (
            f"\n\n📊 *Analisis Trend:*\n"
            f"- BTC: {btc_trend}\n"
            f"- GOLD: {gold_trend}\n"
            f"- Sentimen: {sentiment}\n\n"
            f"⚠️ *Amaran:* Ini adalah analisis automatik. "
            f"Sila buat kajian sendiri sebelum trade."
        )
    else:
        analysis = "\n\n⚠️ Data tidak lengkap. Sila cuba lagi sebentar."

    return (
        f"📈 *Laporan Pasaran Kripto & Komoditi*\n\n"
        f"{btc_msg}\n"
        f"{gold_msg}"
        f"{analysis}"
    )


# Alias untuk keserasian import lama (jangan padam)
gold_market_operators = analyze_gold_btc
