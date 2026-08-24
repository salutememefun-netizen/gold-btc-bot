import requests
import logging
from typing import Optional, List

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_crypto_price(coin_id: str = "bitcoin") -> Optional[float]:
    """
    Mengambil harga semasa cryptocurrency dari CoinGecko API.
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
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
    Fungsi utama untuk analisis harga BTC dan GOLD.
    Dipanggil oleh bot apabila user ketik /analyze.
    """
    # Ambil harga BTC
    btc_price = get_crypto_price("bitcoin")
    
    # Ambil harga GOLD (XAU)
    # Nota: CoinGecko menggunakan 'xau-tether' atau 'gold' untuk data emas
    gold_price = get_crypto_price("xau-tether")
    if not gold_price:
        # Fallback jika ID pertama gagal
        gold_price = get_crypto_price("gold")
    
    # Bina mesej
    btc_msg = f"💰 BTC: ${btc_price:,.2f}" if btc_price else "❌ Gagal ambil harga BTC"
    gold_msg = f"🏆 GOLD: ${gold_price:,.2f}" if gold_price else "❌ Gagal ambil harga GOLD"
    
    # Logik analisis ringkas
    analysis = ""
    if btc_price and gold_price:
        # Logik trend sangat mudah (contoh sahaja)
        btc_trend = "🟢 Naik" if btc_price > 60000 else "🔴 Turun"
        gold_trend = "🟢 Naik" if gold_price > 2300 else "🔴 Turun"
        
        analysis = (
            f"\n\n📊 *Analisis Trend:*\n"
            f"- BTC: {btc_trend}\n"
            f"- GOLD: {gold_trend}\n\n"
            f"⚠️ *Amaran:* Ini adalah analisis automatik. Sila buat kajian sendiri sebelum trade."
        )
    else:
        analysis = "\n\n⚠️ *Analisis:* Tidak dapat menyiapkan laporan penuh (API mungkin sibuk)."

    return f"📈 *Laporan Pasaran Kripto & Komoditi*\n\n{btc_msg}\n{gold_msg}{analysis}"

def calculate_sma(prices: List[float], period: int = 7) -> Optional[float]:
    """Kira Simple Moving Average."""
    if not prices or len(prices) < period:
        return None
    return round(sum(prices[-period:]) / period, 2)

# --- PENYELESAIAN IMPORT ERROR ---
# Fungsi ini wujud semata-mata untuk menyelaraskan dengan kod lama yang mungkin
# cuba mengimport 'gold_market_operators'. Ia hanya merujuk kepada fungsi utama.
gold_market_operators = analyze_gold_btc
