import os
import logging
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

SYMBOLS = {
    "gold": "XAUUSD=X",
    "btc": "BTC-USD"
}


# ============================================================
# YAHOO CANDLE
# ============================================================

def get_candles(asset, interval="15m", period="5d"):

    symbol = SYMBOLS.get(asset)

    if not symbol:
        return [], "Symbol tidak sah"

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + symbol
    )

    params = {
        "interval": interval,
        "range": period,
        "includePrePost": "true"
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

        if response.status_code != 200:

            return [], (
                f"HTTP {response.status_code}"
            )

        data = response.json()

        chart = data.get("chart", {})

        error = chart.get("error")

        if error:

            return [], str(error)

        results = chart.get("result")

        if not results:

            return [], "Yahoo tidak pulangkan result"

        result = results[0]

        timestamps = result.get(
            "timestamp",
            []
        )

        indicators = result.get(
            "indicators",
            {}
        )

        quotes = indicators.get(
            "quote",
            []
        )

        if not quotes:

            return [], "Quote candle kosong"

        quote = quotes[0]

        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])

        candles = []

        length = min(
            len(timestamps),
            len(opens),
            len(highs),
            len(lows),
            len(closes)
        )

        for i in range(length):

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
                "close": float(closes[i])
            })

        if not candles:

            return [], "Candle kosong"

        return candles, None

    except Exception as e:

        logger.exception(
            "Candle error"
        )

        return [], str(e)


# ============================================================
# PRICE
# ============================================================

def get_price(asset):

    candles, error = get_candles(
        asset,
        "5m",
        "1d"
    )

    if not candles:

        return None, error

    return candles[-1]["close"], None


# ============================================================
# EMA
# ============================================================

def calculate_ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema_value = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        ema_value = (
            (price - ema_value)
            * multiplier
        ) + ema_value

    return ema_value


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = (
            values[i] -
            values[i - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

    avg_gain = (
        sum(gains[:period]) /
        period
    )

    avg_loss = (
        sum(losses[:period]) /
        period
    )

    for i in range(period, len(gains)):

        avg_gain = (
            (
                avg_gain *
                (period - 1)
            ) + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss *
                (period - 1)
            ) + losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# ============================================================
# ATR
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    trs = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"] -
            current["low"],

            abs(
                current["high"] -
                previous["close"]
            ),

            abs(
                current["low"] -
                previous["close"]
            )
        )

        trs.append(tr)

    if len(trs) < period:
        return None

    value = (
        sum(trs[:period]) /
        period
    )

    for tr in trs[period:]:

        value = (
            (
                value *
                (period - 1)
            ) + tr
        ) / period

    return value


# ============================================================
# ADX
# ============================================================

def calculate_adx(candles, period=14):

    if len(candles) < 40:
        return None

    trs = []
    plus_dm = []
    minus_dm = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        high_move = (
            current["high"] -
            previous["high"]
        )

        low_move = (
            previous["low"] -
            current["low"]
        )

        tr = max(
            current["high"] -
            current["low"],

            abs(
                current["high"] -
                previous["close"]
            ),

            abs(
                current["low"] -
                previous["close"]
            )
        )

        trs.append(tr)

        if (
            high_move > low_move
            and high_move > 0
        ):

            plus_dm.append(high_move)

        else:

            plus_dm.append(0)

        if (
            low_move > high_move
            and low_move > 0
        ):

            minus_dm.append(low_move)

        else:

            minus_dm.append(0)

    tr_avg = (
        sum(trs[:period]) /
        period
    )

    plus_avg = (
        sum(plus_dm[:period]) /
        period
    )

    minus_avg = (
        sum(minus_dm[:period]) /
        period
    )

    dx = []

    for i in range(period, len(trs)):

        tr_avg = (
            (
                tr_avg *
                (period - 1)
            ) + trs[i]
        ) / period

        plus_avg = (
            (
                plus_avg *
                (period - 1)
            ) + plus_dm[i]
        ) / period

        minus_avg = (
            (
                minus_avg *
                (period - 1)
            ) + minus_dm[i]
        ) / period

        if tr_avg == 0:
            continue

        plus_di = (
            100 *
            plus_avg /
            tr_avg
        )

        minus_di = (
            100 *
            minus_avg /
            tr_avg
        )

        total = (
            plus_di +
            minus_di
        )

        if total == 0:
            continue

        value = (
            100 *
            abs(
                plus_di -
                minus_di
            ) /
            total
        )

        dx.append(value)

    if len(dx) < period:
        return None

    return sum(dx[-period:]) / period


# ============================================================
# MARKET STRUCTURE
# ============================================================

def get_structure(candles):

    if len(candles) < 20:
        return "NEUTRAL"

    recent = candles[-20:]

    first = recent[:10]
    second = recent[10:]

    first_high = max(
        c["high"] for c in first
    )

    second_high = max(
        c["high"] for c in second
    )

    first_low = min(
        c["low"] for c in first
    )

    second_low = min(
        c["low"] for c in second
    )

    if (
        second_high > first_high
        and second_low > first_low
    ):

        return "BULLISH"

    if (
        second_high < first_high
        and second_low < first_low
    ):

        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# ANALYSIS
# ============================================================

def analyze(asset):

    candles15, error15 = get_candles(
        asset,
        "15m",
        "5d"
    )

    candles1h, error1h = get_candles(
        asset,
        "1h",
        "1mo"
    )

    # --------------------------------------------------------
    # DATA CHECK
    # --------------------------------------------------------

    if len(candles15) < 60:

        return {
            "ok": False,
            "error": (
                f"15M candle tidak cukup "
                f"({len(candles15)} candle). "
                f"Sumber: {error15}"
            )
        }

    if len(candles1h) < 50:

        return {
            "ok": False,
            "error": (
                f"1H candle tidak cukup "
                f"({len(candles1h)} candle). "
                f"Sumber: {error1h}"
            )
        }

    # --------------------------------------------------------
    # 15M
    # --------------------------------------------------------

    closes = [
        c["close"]
        for c in candles15
    ]

    price = closes[-1]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    rsi = calculate_rsi(
        closes,
        14
    )

    atr = calculate_atr(
        candles15,
        14
    )

    adx = calculate_adx(
        candles15,
        14
    )

    structure = get_structure(
        candles15
    )

    # --------------------------------------------------------
    # 1H
    # --------------------------------------------------------

    h1_closes = [
        c["close"]
        for c in candles1h
    ]

    h1_ema20 = calculate_ema(
        h1_closes,
        20
    )

    h1_ema50 = calculate_ema(
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

        else:
            h1_trend = "NEUTRAL"

    else:

        h1_trend = "NEUTRAL"

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    buy = 0
    sell = 0

    reasons_buy = []
    reasons_sell = []

    # EMA

    if ema20 > ema50:

        buy += 20

        reasons_buy.append(
            "EMA20 > EMA50"
        )

    elif ema20 < ema50:

        sell += 20

        reasons_sell.append(
            "EMA20 < EMA50"
        )

    # RSI

    if rsi is not None:

        if rsi > 50:

            buy += 15

            reasons_buy.append(
                "RSI > 50"
            )

        elif rsi < 50:

            sell += 15

            reasons_sell.append(
                "RSI < 50"
            )

    # Structure

    if structure == "BULLISH":

        buy += 20

        reasons_buy.append(
            "Structure bullish"
        )

    elif structure == "BEARISH":

        sell += 20

        reasons_sell.append(
            "Structure bearish"
        )

    # H1

    if h1_trend == "BULLISH":

        buy += 20

        reasons_buy.append(
            "1H bullish"
        )

    elif h1_trend == "BEARISH":

        sell += 20

        reasons_sell.append(
            "1H bearish"
        )

    # ADX

    if adx is not None and adx >= 25:

        if buy > sell:

            buy += 15

            reasons_buy.append(
                "ADX trend kuat"
            )

        elif sell > buy:

            sell += 15

            reasons_sell.append(
                "ADX trend kuat"
            )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    if buy >= 60 and buy > sell:

        direction = "BUY"
        confidence = buy
        reasons = reasons_buy

    elif sell >= 60 and sell > buy:

        direction = "SELL"
        confidence = sell
        reasons = reasons_sell

    else:

        direction = "WAIT"
        confidence = max(
            buy,
            sell
        )

        reasons = [
            "Trend belum cukup kuat"
        ]

    # --------------------------------------------------------
    # ATR FALLBACK
    # --------------------------------------------------------

    if atr is None or atr <= 0:

        atr = price * 0.005

    # --------------------------------------------------------
    # LEVELS
    # --------------------------------------------------------

    if direction == "BUY":

        entry_low = price - (
            atr * 0.25
        )

        entry_high = price + (
            atr * 0.25
        )

        sl = price - (
            atr * 1.2
        )

        tp1 = price + (
            atr * 1.2
        )

        tp2 = price + (
            atr * 2
        )

    elif direction == "SELL":

        entry_low = price - (
            atr * 0.25
        )

        entry_high = price + (
            atr * 0.25
        )

        sl = price + (
            atr * 1.2
        )

        tp1 = price - (
            atr * 1.2
        )

        tp2 = price - (
            atr * 2
        )

    else:

        entry_low = price - (
            atr * 0.25
        )

        entry_high = price + (
            atr * 0.25
        )

        sl = None
        tp1 = None
        tp2 = None

    return {
        "ok": True,
        "price": price,
        "direction": direction,
        "confidence": confidence,
        "structure": structure,
        "h1": h1_trend,
        "rsi": rsi,
        "adx": adx,
        "atr": atr,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "reasons": reasons
    }


# ============================================================
# FORMAT
# ============================================================

def format_result(asset, result):

    if not result["ok"]:

        return (
            "❌ *DATA CANDLE GAGAL*\n\n"
            f"{result['error']}\n\n"
            "🔄 Cuba semula beberapa saat lagi."
        )

    name = (
        "GOLD (XAUUSD)"
        if asset == "gold"
        else "BTC"
    )

    direction = result["direction"]

    if direction == "BUY":

        signal_text = "🟢 *BUY*"

    elif direction == "SELL":

        signal_text = "🔴 *SELL*"

    else:

        signal_text = "🟡 *WAIT*"

    text = (
        f"📊 *{name} AI SIGNAL V4*\n\n"

        f"💰 Harga: `${result['price']:,.2f}`\n"
        f"🎯 Signal: {signal_text}\n"
        f"💯 Confidence: `{result['confidence']}%`\n\n"

        f"📐 Structure: `{result['structure']}`\n"
        f"🕐 1H Trend: `{result['h1']}`\n"
        f"📊 RSI: `{result['rsi']:.1f}`\n"
        f"📈 ADX: `{result['adx']:.1f}`\n\n"

        f"🟢 Entry:\n"
        f"`{result['entry_low']:,.2f} – "
        f"{result['entry_high']:,.2f}`\n\n"
    )

    if direction != "WAIT":

        text += (
            f"🛑 SL:\n"
            f"`{result['sl']:,.2f}`\n\n"

            f"🎯 TP1:\n"
            f"`{result['tp1']:,.2f}`\n\n"

            f"🎯 TP2:\n"
            f"`{result['tp2']:,.2f}`\n\n"
        )

    text += "🧠 *Sebab signal:*\n"

    for reason in result["reasons"]:

        text += f"• {reason}\n"

    text += (
        "\n⚠️ Analisis teknikal sahaja. "
        "Bukan jaminan profit.\n"
        "🚫 Tiada auto-trading."
    )

    return text


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 *GOLD & BTC SIGNAL BOT V4*\n\n"
        "/price — Harga semasa\n"
        "/signal gold — Signal Gold\n"
        "/signal btc — Signal BTC\n"
        "/news — News monitor\n\n"
        "📊 Engine: 15M + 1H\n"
        "🧠 EMA + RSI + ADX + Structure + ATR\n"
        "🚫 Tiada auto-trading.",
        parse_mode="Markdown"
    )


# ============================================================
# PRICE
# ============================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    gold, gold_error = get_price("gold")
    btc, btc_error = get_price("btc")

    text = "📈 *HARGA SEMASA*\n\n"

    if gold is not None:

        text += (
            f"🥇 Gold XAUUSD\n"
            f"`${gold:,.2f}`\n\n"
        )

    else:

        text += (
            "🥇 Gold: ❌ Gagal\n"
            f"`{gold_error}`\n\n"
        )

    if btc is not None:

        text += (
            f"₿ Bitcoin BTC\n"
            f"`${btc:,.2f}`\n"
        )

    else:

        text += (
            "₿ BTC: ❌ Gagal\n"
            f"`{btc_error}`\n"
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

    if asset not in SYMBOLS:

        await update.message.reply_text(
            "❌ Asset tidak disokong.\n\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    status = await update.message.reply_text(
        "🧠 *MENGANALISIS MARKET...*\n\n"
        f"🪙 Asset: `{asset.upper()}`\n"
        "📊 Timeframe: `15M + 1H`\n"
        "⏳ Mengambil candle sebenar...",
        parse_mode="Markdown"
    )

    result = analyze(asset)

    message = format_result(
        asset,
        result
    )

    try:

        await status.edit_text(
            message,
            parse_mode="Markdown"
        )

    except Exception:

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

    await update.message.reply_text(
        "📰 *NEWS MONITOR V4*\n\n"
        "🥇 GOLD\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• CPI\n"
        "• NFP\n"
        "• Interest Rate\n\n"
        "₿ BTC\n"
        "• ETF Flow\n"
        "• Funding Rate\n"
        "• BTC Dominance\n"
        "• US Macro\n\n"
        "⚠️ News engine belum disambungkan.",
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
    print("======================================")
    print("🤖 GOLD & BTC SIGNAL BOT V4")
    print("======================================")

    if not TOKEN:

        print("❌ BOT_TOKEN tidak dijumpai.")

        return

    print("✅ BOT_TOKEN berjaya dibaca.")
    print("🚀 Starting bot...")

    application = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "price",
            price
        )
    )

    application.add_handler(
        CommandHandler(
            "signal",
            signal
        )
    )

    application.add_handler(
        CommandHandler(
            "news",
            news
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("📡 Telegram polling aktif.")
    print("======================================")

    application.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
