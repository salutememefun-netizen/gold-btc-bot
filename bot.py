import os
import logging
import requests
import math

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# ============================================================
# SYMBOLS
# ============================================================

YAHOO_SYMBOLS = {
    "gold": "XAUUSD=X",
    "btc": "BTC-USD",
}

# ============================================================
# GENERIC HTTP
# ============================================================

def yahoo_candles(symbol, interval="15m", range_value="5d"):

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    params = {
        "interval": interval,
        "range": range_value,
        "includePrePost": "true",
        "events": "div,splits"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        result = data["chart"]["result"]

        if not result:
            return []

        result = result[0]

        timestamps = result.get("timestamp", [])
        quote = result["indicators"]["quote"][0]

        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])

        candles = []

        for i in range(len(timestamps)):

            if (
                i >= len(opens)
                or i >= len(highs)
                or i >= len(lows)
                or i >= len(closes)
            ):
                continue

            if (
                opens[i] is None
                or highs[i] is None
                or lows[i] is None
                or closes[i] is None
            ):
                continue

            candles.append({
                "time": timestamps[i],
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
            })

        return candles

    except Exception as e:

        logger.error(
            f"Yahoo candle error {symbol}: {e}"
        )

        return []


# ============================================================
# PRICE
# ============================================================

def get_live_price(asset):

    symbol = YAHOO_SYMBOLS[asset]

    candles = yahoo_candles(
        symbol,
        "1m",
        "1d"
    )

    if not candles:
        return None

    return candles[-1]["close"]


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    value = sum(values[:period]) / period

    for price in values[period:]:

        value = (
            (price - value) * multiplier
            + value
        )

    return value


# ============================================================
# RSI
# ============================================================

def rsi(values, period=14):

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = values[i] - values[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)

        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ============================================================
# ATR
# ============================================================

def atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    trs = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"] - current["low"],
            abs(
                current["high"]
                - previous["close"]
            ),
            abs(
                current["low"]
                - previous["close"]
            )
        )

        trs.append(tr)

    if len(trs) < period:
        return None

    value = sum(trs[:period]) / period

    for tr in trs[period:]:

        value = (
            (value * (period - 1))
            + tr
        ) / period

    return value


# ============================================================
# ADX
# ============================================================

def adx(candles, period=14):

    if len(candles) < period * 2:
        return None

    trs = []
    plus_dm = []
    minus_dm = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        high_diff = (
            current["high"]
            - previous["high"]
        )

        low_diff = (
            previous["low"]
            - current["low"]
        )

        tr = max(
            current["high"] - current["low"],
            abs(
                current["high"]
                - previous["close"]
            ),
            abs(
                current["low"]
                - previous["close"]
            )
        )

        trs.append(tr)

        plus_dm.append(
            high_diff
            if high_diff > low_diff
            and high_diff > 0
            else 0
        )

        minus_dm.append(
            low_diff
            if low_diff > high_diff
            and low_diff > 0
            else 0
        )

    if len(trs) < period * 2:
        return None

    tr_avg = sum(trs[:period]) / period
    plus_avg = sum(plus_dm[:period]) / period
    minus_avg = sum(minus_dm[:period]) / period

    dx_values = []

    for i in range(period, len(trs)):

        tr_avg = (
            (tr_avg * (period - 1))
            + trs[i]
        ) / period

        plus_avg = (
            (plus_avg * (period - 1))
            + plus_dm[i]
        ) / period

        minus_avg = (
            (minus_avg * (period - 1))
            + minus_dm[i]
        ) / period

        if tr_avg == 0:
            continue

        plus_di = (
            100 * plus_avg / tr_avg
        )

        minus_di = (
            100 * minus_avg / tr_avg
        )

        denominator = plus_di + minus_di

        if denominator == 0:
            continue

        dx = (
            100
            * abs(plus_di - minus_di)
            / denominator
        )

        dx_values.append(dx)

    if len(dx_values) < period:
        return None

    return sum(dx_values[-period:]) / period


# ============================================================
# MARKET STRUCTURE
# ============================================================

def market_structure(candles):

    if len(candles) < 10:
        return "NEUTRAL"

    recent = candles[-10:]

    highs = [
        c["high"]
        for c in recent
    ]

    lows = [
        c["low"]
        for c in recent
    ]

    first_half_high = max(
        highs[:5]
    )

    second_half_high = max(
        highs[5:]
    )

    first_half_low = min(
        lows[:5]
    )

    second_half_low = min(
        lows[5:]
    )

    if (
        second_half_high > first_half_high
        and second_half_low > first_half_low
    ):
        return "BULLISH"

    if (
        second_half_high < first_half_high
        and second_half_low < first_half_low
    ):
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# ANALYZE
# ============================================================

def analyze_asset(asset):

    symbol = YAHOO_SYMBOLS[asset]

    candles_15m = yahoo_candles(
        symbol,
        "15m",
        "5d"
    )

    candles_1h = yahoo_candles(
        symbol,
        "1h",
        "1mo"
    )

    if len(candles_15m) < 60:
        return None

    closes = [
        c["close"]
        for c in candles_15m
    ]

    price = closes[-1]

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    rsi_value = rsi(
        closes,
        14
    )

    atr_value = atr(
        candles_15m,
        14
    )

    adx_value = adx(
        candles_15m,
        14
    )

    structure = market_structure(
        candles_15m
    )

    # --------------------------------------------------------
    # 1H TREND
    # --------------------------------------------------------

    h1_trend = "NEUTRAL"

    if len(candles_1h) >= 50:

        h1_closes = [
            c["close"]
            for c in candles_1h
        ]

        h1_ema20 = ema(
            h1_closes,
            20
        )

        h1_ema50 = ema(
            h1_closes,
            50
        )

        if (
            h1_ema20 is not None
            and h1_ema50 is not None
        ):

            if h1_ema20 > h1_ema50:
                h1_trend = "BULLISH"

            elif h1_ema20 < h1_ema50:
                h1_trend = "BEARISH"

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    buy_score = 0
    sell_score = 0

    reasons_buy = []
    reasons_sell = []

    # EMA

    if ema20 and ema50:

        if ema20 > ema50:

            buy_score += 20
            reasons_buy.append(
                "EMA20 > EMA50"
            )

        elif ema20 < ema50:

            sell_score += 20
            reasons_sell.append(
                "EMA20 < EMA50"
            )

    # RSI

    if rsi_value is not None:

        if 50 < rsi_value < 70:

            buy_score += 15
            reasons_buy.append(
                "RSI bullish"
            )

        elif 30 < rsi_value < 50:

            sell_score += 15
            reasons_sell.append(
                "RSI bearish"
            )

    # ADX

    if adx_value is not None:

        if adx_value >= 25:

            if buy_score > sell_score:

                buy_score += 15

                reasons_buy.append(
                    "ADX trend kuat"
                )

            elif sell_score > buy_score:

                sell_score += 15

                reasons_sell.append(
                    "ADX trend kuat"
                )

    # Structure

    if structure == "BULLISH":

        buy_score += 20
        reasons_buy.append(
            "Market structure bullish"
        )

    elif structure == "BEARISH":

        sell_score += 20
        reasons_sell.append(
            "Market structure bearish"
        )

    # 1H

    if h1_trend == "BULLISH":

        buy_score += 20
        reasons_buy.append(
            "1H trend bullish"
        )

    elif h1_trend == "BEARISH":

        sell_score += 20
        reasons_sell.append(
            "1H trend bearish"
        )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    if (
        buy_score >= 55
        and buy_score > sell_score
    ):

        direction = "BUY"
        confidence = buy_score
        reasons = reasons_buy

    elif (
        sell_score >= 55
        and sell_score > buy_score
    ):

        direction = "SELL"
        confidence = sell_score
        reasons = reasons_sell

    else:

        direction = "WAIT"

        confidence = max(
            buy_score,
            sell_score
        )

        reasons = [
            "Trend belum cukup kuat"
        ]

    # --------------------------------------------------------
    # PRICE LEVELS
    # --------------------------------------------------------

    if atr_value is None:

        atr_value = price * 0.005

    if direction == "BUY":

        entry_low = price - (
            atr_value * 0.25
        )

        entry_high = price + (
            atr_value * 0.25
        )

        sl = price - (
            atr_value * 1.2
        )

        tp1 = price + (
            atr_value * 1.2
        )

        tp2 = price + (
            atr_value * 2.0
        )

    elif direction == "SELL":

        entry_low = price - (
            atr_value * 0.25
        )

        entry_high = price + (
            atr_value * 0.25
        )

        sl = price + (
            atr_value * 1.2
        )

        tp1 = price - (
            atr_value * 1.2
        )

        tp2 = price - (
            atr_value * 2.0
        )

    else:

        entry_low = price - (
            atr_value * 0.25
        )

        entry_high = price + (
            atr_value * 0.25
        )

        sl = None
        tp1 = None
        tp2 = None

    return {
        "price": price,
        "direction": direction,
        "confidence": confidence,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,
        "structure": structure,
        "h1_trend": h1_trend,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "reasons": reasons,
    }


# ============================================================
# FORMAT SIGNAL
# ============================================================

def format_signal(asset, result):

    if result is None:

        return (
            "❌ Data candle tidak tersedia.\n"
            "Cuba semula dalam beberapa saat."
        )

    name = (
        "GOLD (XAUUSD)"
        if asset == "gold"
        else "BTC"
    )

    price = result["price"]

    direction = result["direction"]

    confidence = result["confidence"]

    structure = result["structure"]

    h1_trend = result["h1_trend"]

    rsi_value = result["rsi"]

    adx_value = result["adx"]

    entry_low = result["entry_low"]

    entry_high = result["entry_high"]

    message = (
        f"📊 *{name} AI SIGNAL V3*\n\n"

        f"💰 Harga: `${price:,.2f}`\n\n"
    )

    if direction == "BUY":

        message += "🟢 *SIGNAL: BUY*\n\n"

    elif direction == "SELL":

        message += "🔴 *SIGNAL: SELL*\n\n"

    else:

        message += "🟡 *SIGNAL: WAIT*\n\n"

    message += (
        f"💯 *Confidence:* `{confidence}%`\n"
        f"📐 *Structure:* `{structure}`\n"
        f"🕐 *1H Trend:* `{h1_trend}`\n"
        f"📊 *RSI:* `{rsi_value:.1f}`\n"
        f"📈 *ADX:* `{adx_value:.1f}`\n\n"
    )

    message += (
        f"🟢 *Entry Zone*\n"
        f"`{entry_low:,.2f} – {entry_high:,.2f}`\n\n"
    )

    if direction != "WAIT":

        message += (
            f"🛑 *Stop Loss*\n"
            f"`{result['sl']:,.2f}`\n\n"

            f"🎯 *TP1*\n"
            f"`{result['tp1']:,.2f}`\n\n"

            f"🎯 *TP2*\n"
            f"`{result['tp2']:,.2f}`\n\n"
        )

    message += "🧠 *Analysis:*\n"

    for reason in result["reasons"]:

        message += f"• {reason}\n"

    message += (
        "\n⚠️ Signal berdasarkan data teknikal. "
        "Bukan jaminan profit."
    )

    return message


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🤖 *GOLD & BTC SIGNAL BOT V3*\n\n"

        "📌 Commands:\n\n"

        "/price\n"
        "➡️ Harga semasa\n\n"

        "/signal gold\n"
        "➡️ AI signal Gold\n\n"

        "/signal btc\n"
        "➡️ AI signal BTC\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 Technical engine aktif\n"
        "📊 15M + 1H analysis\n"
        "🚫 Tiada auto-trading"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# PRICE
# ============================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    gold = get_live_price("gold")
    btc = get_live_price("btc")

    text = "📈 *HARGA SEMASA*\n\n"

    if gold is not None:

        text += (
            f"🥇 *Gold XAUUSD*\n"
            f"`${gold:,.2f}`\n\n"
        )

    else:

        text += (
            "🥇 Gold: ❌ Data gagal\n\n"
        )

    if btc is not None:

        text += (
            f"₿ *Bitcoin BTC*\n"
            f"`${btc:,.2f}`\n"
        )

    else:

        text += (
            "₿ BTC: ❌ Data gagal\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# SIGNAL
# ============================================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "❌ Pilih asset:\n\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    asset = context.args[0].lower()

    if asset not in ["gold", "btc"]:

        await update.message.reply_text(
            "❌ Asset tidak disokong.\n\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    await update.message.reply_text(
        "🧠 Menganalisis market...\n"
        "📊 15M + 1H\n"
        "⏳ Sila tunggu..."
    )

    result = analyze_asset(asset)

    message = format_signal(
        asset,
        result
    )

    await update.message.reply_text(
        message,
        parse_mode="Markdown"
    )


# ============================================================
# NEWS
# ============================================================

async def news(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "📰 *NEWS MONITOR V3*\n\n"

        "🥇 *GOLD*\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• US CPI\n"
        "• NFP\n"
        "• Interest rate\n\n"

        "₿ *BITCOIN*\n"
        "• ETF flow\n"
        "• Funding rate\n"
        "• BTC dominance\n"
        "• US macro data\n\n"

        "⚠️ News engine akan ditambah "
        "selepas technical engine stabil."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# ERROR
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram error:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("==========================================")
    print("🤖 GOLD & BTC TELEGRAM BOT V3")
    print("==========================================")

    if not TOKEN:

        print("❌ BOT_TOKEN TIDAK DIJUMPAI!")

        return

    print("✅ BOT_TOKEN berjaya dibaca!")
    print("🤖 Bot sedang dimulakan...")

    try:

        application = (
            Application
            .builder()
            .token(TOKEN)
            .build()
        )

        application.add_handler(
            CommandHandler("start", start)
        )

        application.add_handler(
            CommandHandler("price", price)
        )

        application.add_handler(
            CommandHandler("signal", signal)
        )

        application.add_handler(
            CommandHandler("news", news)
        )

        application.add_error_handler(
            error_handler
        )

        print("🚀 Bot sedang berjalan!")
        print("📡 Telegram polling aktif!")
        print("==========================================")

        application.run_polling(
            drop_pending_updates=True
        )

    except Exception as e:

        print("")
        print("❌ BOT ERROR")
        print(str(e))
        print("")

        logger.exception(
            "Fatal bot error"
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
