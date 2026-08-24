import requests
import logging
from typing import Optional, Dict, Any

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_crypto_price(coin_id: str = "bitcoin") -> Optional[float]:
    """
    Mengambil harga semasa cryptocurrency dari CoinGecko API.
    
    Args:
        coin_id: ID cryptocurrency (contoh: 'bitcoin', 'ethereum', 'xau-tether')
    
    Returns:
        Harga dalam USD atau None jika gagal.
    """
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if coin_id in data and "usd" in data[coin_id]:
            price = data[coin_id]["usd"]
            logger.info(f"Harga {coin_id}: ${price:,.2f}")
            return price
        else:
            logger.warning(f"Data harga tidak dijumpai untuk {coin_id}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Ralat rangkaian semasa mengambil harga {coin_id}: {e}")
        return None
    except ValueError as e:
        logger.error(f"Ralat parsing JSON untuk {coin_id}: {e}")
        return None

def analyze_gold_btc() -> str:
    """
    Analisis harga semasa untuk Bitcoin (BTC) dan Emas (GOLD/XAU).
    
    Returns:
        String laporan analisis dalam format teks.
    """
    # Ambil harga BTC
    btc_price = get_crypto_price("bitcoin")
    
    # Ambil harga GOLD (menggunakan ID 'xau-tether' sebagai proxy untuk XAU/USD)
    # Nota: CoinGecko kadang-kala tidak menyediakan data XAU langsung, 
    # jadi kita guna token yang dipautkan pada emas.
    gold_price = get_crypto_price("xau-tether")
    
    # Bina mesej laporan
    btc_msg = f"💰 BTC: ${btc_price:,.2f}" if btc_price else "❌ Gagal ambil harga BTC"
    gold_msg = f"🏆 GOLD (XAU): ${gold_price:,.2f}" if gold_price else "❌ Gagal ambil harga GOLD"
    
    # Analisis ringkas
    analysis = ""
    if btc_price and gold_price:
        btc_change = "naik" if btc_price > 60000 else "turun" # Logik ringkas
        gold_change = "naik" if gold_price > 2300 else "turun" # Logik ringkas
        
        analysis = (
            f"\n\n📊 *Analisis Pasaran:*\n"
            f"- BTC sedang {btc_change} (Trend: {btc_price:,.0f})\n"
            f"- GOLD sedang {gold_change} (Trend: {gold_price:,.0f})\n"
            f"- Cadangan: Pantau volatiliti sebelum membuat keputusan."
        )
    else:
        analysis = "\n\n⚠️ *Analisis:* Tidak dapat menyiapkan laporan penuh disebabkan ralat data."

    return f"📈 Laporan Pasaran Kripto & Komoditi\n\n{btc_msg}\n{gold_msg}{analysis}"

def calculate_simple_moving_average(prices: list, period: int = 7) -> Optional[float]:
    """
    Mengira Simple Moving Average (SMA) untuk analisis trend.
    
    Args:
        prices: Senarai harga historis.
        period: Tempoh untuk pengiraan SMA.
    
    Returns:
        Nilai SMA atau None jika data tidak mencukupi.
    """
    if not prices or len(prices) < period:
        return None
    
    # Ambil 'period' harga terakhir dan kira purata
    recent_prices = prices[-period:]
    sma = sum(recent_prices) / period
    return round(sma, 2)

def format_currency(value: float, currency: str = "USD") -> str:
    """
    Memformat nombor kepada format mata wang.
    
    Args:
        value: Nilai nombor.
        currency: Kod mata wang (USD, MYR, dll).
    
    Returns:
        String format mata wang.
    """
    if currency == "USD":
        return f"${value:,.2f}"
    elif currency == "MYR":
        return f"RM{value:,.2f}"
    else:
        return f"{currency} {value:,.2f}"

# Contoh fungsi tambahan jika anda perlukan logik khusus
def get_market_sentiment(btc_price: float, gold_price: float) -> str:
    """
    Menentukan sentimen pasaran berdasarkan harga.
    """
    if btc_price > 65000 and gold_price > 2400:
        return "🚀 *Bullish:* Kedua-dua aset menunjukkan kekuatan."
    elif btc_price < 55000 and gold_price < 2200:
        return "📉 *Bearish:* Pasaran sedang lemah."
    else:
        return "⚖️ *Neutral:* Pasaran dalam keadaan tidak menentu."
