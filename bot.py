import os
import requests
import pandas as pd
import numpy as np
from telegram import Bot
from datetime import datetime
import asyncio

# ==============================
# KONFIGURASI (dari GitHub Secrets)
# ==============================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
SYMBOL = "BTC/USDT"

# ==============================
# FUNGSI DATA HARGA (BINANCE)
# ==============================

def get_price_data():
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "limit": 100
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        closes = [float(c[4]) for c in data]
        highs  = [float(c[2]) for c in data]
        lows   = [float(c[3]) for c in data]
        volumes = [float(c[5]) for c in data]
        return closes, highs, lows, volumes
    except Exception as e:
        raise Exception(f"Gagal dapatkan data harga: {e}")

# ==============================
# FUNGSI INDIKATOR TEKNIKAL
# ==============================

def calculate_rsi(closes, period=14):
    closes = np.array(closes)
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        return 100.0

    rs  = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calculate_moving_average(closes, period):
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)

def calculate_ema(closes, period):
    series = pd.Series(closes)
    ema = series.ewm(span=period, adjust=False).mean()
    return round(ema.iloc[-1], 2)

def calculate_macd(closes):
    closes = np.array(closes)
    series = pd.Series(closes)
    ema12  = series.ewm(span=12, adjust=False).mean()
    ema26  = series.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram   = macd_line - signal_line
    return (
        round(macd_line.iloc[-1], 2),
        round(signal_line.iloc[-1], 2),
        round(histogram.iloc[-1], 2)
    )

def calculate_bollinger_bands(closes, period=20):
    closes = np.array(closes[-period:])
    ma     = np.mean(closes)
    std    = np.std(closes)
    upper  = round(ma + (2 * std), 2)
    lower  = round(ma - (2 * std), 2)
    mid    = round(ma, 2)
    return upper, mid, lower

def calculate_stochastic(closes, highs, lows, period=14):
    recent_closes = closes[-period:]
    recent_highs  = highs[-period:]
    recent_lows   = lows[-period:]

    highest_high = max(recent_highs)
    lowest_low   = min(recent_lows)
    current      = recent_closes[-1]

    if highest_high == lowest_low:
        return 50.0

    k = ((current - lowest_low) / (highest_high - lowest_low)) * 100
    return round(k, 2)

def calculate_atr(highs, lows, closes, period=14):
    tr_list = []
    for i in range(1, len(closes)):
        high_low   = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i - 1])
        low_close  = abs(lows[i] - closes[i - 1])
        tr_list.append(max(high_low, high_close, low_close))
    atr = np.mean(tr_list[-period:])
    return round(atr, 2)

def calculate_support_resistance(highs, lows):
    support    = round(min(lows[-20:]), 2)
    resistance = round(max(highs[-20:]), 2)
    return support, resistance

def calculate_volume_signal(volumes):
    avg_volume     = np.mean(volumes[-20:])
    current_volume = volumes[-1]
    if current_volume > avg_volume * 1.5:
        return "TINGGI 🔥", round(current_volume, 2), round(avg_volume, 2)
    elif current_volume < avg_volume * 0.5:
        return "RENDAH 💤", round(current_volume, 2), round(avg_volume, 2)
    else:
        return "NORMAL ➡️", round(current_volume, 2), round(avg_volume, 2)

# ==============================
# FUNGSI BERITA PASARAN
# ==============================

def get_market_news():
    if not NEWS_API_KEY:
        return []
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "bitcoin crypto market",
        "apiKey": NEWS_API_KEY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        articles = response.json().get("articles", [])
        return [a["title"] for a in articles[:5]]
    except:
        return []

def analyze_news_sentiment(headlines):
    bearish_words = [
        "crash", "drop", "fall", "bear", "down",
        "loss", "ban", "hack", "fear", "sell", "dump"
    ]
    bullish_words = [
        "surge", "rally", "bull", "up", "gain",
        "rise", "adoption", "buy", "pump", "ath", "record"
    ]

    bearish_count = 0
    bullish_count = 0

    for headline in headlines:
        h = headline.lower()
        bearish_count += sum(1 for w in bearish_words if w in h)
        bullish_count += sum(1 for w in bullish_words if w in h)

    if bearish_count > bullish_count:
        return "BEARISH ⚠️", bullish_count, bearish_count
    elif bullish_count > bearish_count:
        return "BULLISH ✅", bullish_count, bearish_count
    else:
        return "NEUTRAL ➡️", bullish_count, bearish_count

# ==============================
# FUNGSI JANA ISYARAT
# ==============================

def generate_signal(
    rsi, stoch, macd, signal_line, histogram,
    current_price, ma20, ma50, ema20,
    support, resistance, bb_upper, bb_lower,
    volume_status, sentiment
):
    buy_points  = 0
    sell_points = 0
    reasons     = []

    # RSI
    if rsi < 30:
        buy_points += 2
        reasons.append(f"RSI Oversold ({rsi})")
    elif rsi > 70:
        sell_points += 2
        reasons.append(f"RSI Overbought ({rsi})")
    elif rsi < 45:
        buy_points += 1
        reasons.append(f"RSI Condong Beli ({rsi})")
    elif rsi > 55:
        sell_points += 1
        reasons.append(f"RSI Condong Jual ({rsi})")

    # Stochastic
    if stoch < 20:
        buy_points += 2
        reasons.append(f"Stochastic Oversold ({stoch})")
    elif stoch > 80:
        sell_points += 2
        reasons.append(f"Stochastic Overbought ({stoch})")

    # MACD
    if macd > signal_line and histogram > 0:
        buy_points += 2
        reasons.append("MACD Bullish Cross")
    elif macd < signal_line and histogram < 0:
        sell_points += 2
        reasons.append("MACD Bearish Cross")

    # Moving Average
    if ma20 and ma50:
        if ma20 > ma50 and current_price > ma20:
            buy_points += 1
            reasons.append("Harga Atas MA20 & MA50 (Uptrend)")
        elif ma20 < ma50 and current_price < ma20:
            sell_points += 1
            reasons.append("Harga Bawah MA20 & MA50 (Downtrend)")

    # EMA
    if current_price > ema20:
        buy_points += 1
        reasons.append("Harga Atas EMA20")
    else:
        sell_points += 1
        reasons.append("Harga Bawah EMA20")

    # Support & Resistance
    if current_price <= support * 1.01:
        buy_points += 2
        reasons.append(f"Dekat Zon Support (${support:,.2f})")
    elif current_price >= resistance * 0.99:
        sell_points += 2
        reasons.append(f"Dekat Zon Resistance (${resistance:,.2f})")

    # Bollinger Bands
    if current_price <= bb_lower:
        buy_points += 2
        reasons.append("Harga Sentuh Lower Bollinger Band")
    elif current_price >= bb_upper:
        sell_points += 2
        reasons.append("Harga Sentuh Upper Bollinger Band")

    # Volume
    if "TINGGI" in volume_status:
        if buy_points > sell_points:
            buy_points += 1
            reasons.append("Volume Tinggi Sokong BUY")
        elif sell_points > buy_points:
            sell_points += 1
            reasons.append("Volume Tinggi Sokong SELL")

    # Sentimen Berita
    if "BULLISH" in sentiment:
        buy_points += 1
        reasons.append("Sentimen Berita Positif")
    elif "BEARISH" in sentiment:
        sell_points += 1
        reasons.append("Sentimen Berita Negatif")

    # Tentukan isyarat akhir
    if buy_points >= 5 and buy_points > sell_points:
        signal   = "🟢 BUY"
        strength = "KUAT" if buy_points >= 7 else "SEDERHANA"
        entry    = current_price
        tp1      = round(current_price * 1.02, 2)
        tp2      = round(current_price * 1.04, 2)
        tp3      = round(current_price * 1.06, 2)
        sl       = round(current_price * 0.98, 2)
    elif sell_points >= 5 and sell_points > buy_points:
        signal   = "🔴 SELL"
        strength = "KUAT" if sell_points >= 7 else "SEDERHANA"
        entry    = current_price
        tp1      = round(current_price * 0.98, 2)
        tp2      = round(current_price * 0.96, 2)
        tp3      = round(current_price * 0.94, 2)
        sl       = round(current_price * 1.02, 2)
    else:
        signal   = "⏳ TUNGGU"
        strength = "TIADA ISYARAT JELAS"
        entry    = current_price
        tp1 = tp2 = tp3 = sl = None

    return signal, strength, entry, tp1, tp2, tp3, sl, reasons, buy_points, sell_points

# ==============================
# FUNGSI HANTAR KE TELEGRAM
# ==============================

async def send_signal():
    bot = Bot(token=TOKEN)

    try:
        # Dapatkan data
        closes, highs, lows, volumes = get_price_data()
        current_price = closes[-1]

        # Kira semua indikator
        rsi               = calculate_rsi(closes)
        ma20              = calculate_moving_average(closes, 20)
        ma50              = calculate_moving_average(closes, 50)
        ema20             = calculate_ema(closes, 20)
        macd, sig, hist   = calculate_macd(closes)
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(closes)
        stoch             = calculate_stochastic(closes, highs, lows)
        atr               = calculate_atr(highs, lows, closes)
        support, resistance = calculate_support_resistance(highs, lows)
        vol_status, cur_vol, avg_vol = calculate_volume_signal(volumes)

        # Berita & sentimen
        headlines   = get_market_news()
        sentiment, bull_c, bear_c = analyze_news_sentiment(headlines)

        # Jana isyarat
        signal, strength, entry, tp1, tp2, tp3, sl, reasons, buy_pts, sell_pts = generate_signal(
            rsi, stoch, macd, sig, hist,
            current_price, ma20, ma50, ema20,
            support, resistance, bb_upper, bb_lower,
            vol_status, sentiment
        )

        now = datetime.now().strftime("%d/%m/%Y %H:%M UTC")

        # Format mesej
        message = f"""
📊 *SIGNAL BOT REPORT*
🕐 {now}
━━━━━━━━━━━━━━━━━
📌 *Aset:* `{SYMBOL}`
💰 *Harga Semasa:* `${current_price:,.2f}`

━━━━━━━━━━━━━━━━━
📈 *ANALISIS TEKNIKAL*
• RSI (14):          `{rsi}`
• Stochastic:        `{stoch}`
• MACD:              `{macd}`
• Signal Line:       `{sig}`
• Histogram:         `{hist}`
• MA20:              `${ma20:,.2f}`
• MA50:              `${ma50:,.2f}`
• EMA20:             `${ema20:,.2f}`
• BB Upper:          `${bb_upper:,.2f}`
• BB Lower:          `${bb_lower:,.2f}`
• Support:           `${support:,.2f}`
• Resistance:        `${resistance:,.2f}`
• ATR:               `{atr}`

━━━━━━━━━━━━━━━━━
📦 *VOLUME*
• Status:            {vol_status}
• Semasa:            `{cur_vol:,.2f}`
• Purata (20):       `{avg_vol:,.2f}`

━━━━━━━━━━━━━━━━━
📰 *SENTIMEN BERITA*
• Status:            {sentiment}
• Bullish Signals:   `{bull_c}`
• Bearish Signals:   `{bear_c}`
"""

        if headlines:
            message += "\n📋 *Tajuk Berita Terkini:*\n"
            for i, h in enumerate(headlines[:3], 1):
                message += f"{i}. {h[:60]}...\n"

        message += f"""
━━━━━━━━━━━━━━━━━
🎯 *ISYARAT UTAMA*
• Signal:            *{signal}*
• Kekuatan:          *{strength}*
• Buy Points:        `{buy_pts}`
• Sell Points:       `{sell_pts}`
"""

        if tp1 and sl:
            message += f"""• Entry:             `${entry:,.2f}`
• Take Profit 1:     `${tp1:,.2f}` (+2%)
• Take Profit 2:     `${tp2:,.2f}` (+4%)
• Take Profit 3:     `${tp3:,.2f}` (+6%)
• Stop Loss:         `${sl:,.2f}` (-2%)
"""

        message += "\n📋 *SEBAB ISYARAT:*\n"
        for r in reasons:
            message += f"• {r}\n"

        message += "\n⚠️ *DISCLAIMER: Ini bukan nasihat kewangan. Buat kajian sendiri sebelum trade.*"

        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
        print(f"✅ Isyarat berjaya dihantar: {signal}")

    except Exception as e:
        print(f"❌ Ralat: {e}")
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=f"❌ Bot ralat: {str(e)}"
            )
        except:
            pass

if __name__ == "__main__":
    asyncio.run(send_signal())
