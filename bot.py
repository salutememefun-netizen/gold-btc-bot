import os
import requests
import pandas as pd
import numpy as np

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ============================================================
# DOWNLOAD CANDLE DATA
# ============================================================

def get_candles(symbol, interval="5m", range_value="1d"):

    try:

        url = YAHOO_URL.format(symbol)

        params = {
            "interval": interval,
            "range": range_value,
            "includePrePost": "true",
            "events": "div,splits"
        }

        r = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=15
        )

        r.raise_for_status()

        data = r.json()

        result = data["chart"]["result"][0]

        timestamps = result["timestamp"]

        quote = result["indicators"]["quote"][0]

        df = pd.DataFrame({
            "timestamp": pd.to_datetime(
                timestamps,
                unit="s",
                utc=True
            ),
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "volume": quote.get(
                "volume",
                [0] * len(timestamps)
            )
        })

        df = df.dropna()

        df = df.set_index("timestamp")

        return df

    except Exception as e:

        print(f"DATA ERROR {symbol}: {e}")

        return None


# ============================================================
# RESAMPLE TIMEFRAME
# ============================================================

def resample_candles(df, timeframe):

    if df is None or df.empty:
        return None

    rule_map = {
        "M5": "5min",
        "M15": "15min",
        "H1": "1h",
        "H4": "4h"
    }

    rule = rule_map.get(timeframe)

    if rule is None:
        return None

    result = df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    })

    result = result.dropna()

    return result


# ============================================================
# EMA
# ============================================================

def calculate_ema(df, period):

    return df["close"].ewm(
        span=period,
        adjust=False
    ).mean()


# ============================================================
# RSI
# ============================================================

def calculate_rsi(df, period=14):

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


# ============================================================
# ATR
# ============================================================

def calculate_atr(df, period=14):

    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]

    tr2 = (
        df["high"] - previous_close
    ).abs()

    tr3 = (
        df["low"] - previous_close
    ).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()


# ============================================================
# MARKET STRUCTURE
# ============================================================

def detect_structure(df):

    if len(df) < 30:
        return "NEUTRAL", 0

    recent = df.tail(30)

    highs = recent["high"]
    lows = recent["low"]

    last_close = recent["close"].iloc[-1]

    previous_high = highs.iloc[:-3].max()
    previous_low = lows.iloc[:-3].min()

    score = 0

    if last_close > previous_high:
        return "BULLISH BOS", 2

    if last_close < previous_low:
        return "BEARISH BOS", -2

    # Higher highs / higher lows
    if highs.iloc[-1] > highs.iloc[-5]:
        score += 1

    if lows.iloc[-1] > lows.iloc[-5]:
        score += 1

    if score >= 2:
        return "BULLISH", 1

    # Lower highs / lower lows
    score = 0

    if highs.iloc[-1] < highs.iloc[-5]:
        score -= 1

    if lows.iloc[-1] < lows.iloc[-5]:
        score -= 1

    if score <= -2:
        return "BEARISH", -1

    return "NEUTRAL", 0


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def detect_liquidity_sweep(df):

    if len(df) < 15:
        return "NONE", 0

    recent = df.tail(15)

    last = recent.iloc[-1]

    previous_high = recent["high"].iloc[:-1].max()
    previous_low = recent["low"].iloc[:-1].min()

    # Sweep high kemudian close bawah
    if (
        last["high"] > previous_high
        and last["close"] < previous_high
    ):
        return "BUY-SIDE SWEEP", -1

    # Sweep low kemudian close atas
    if (
        last["low"] < previous_low
        and last["close"] > previous_low
    ):
        return "SELL-SIDE SWEEP", 1

    return "NONE", 0


# ============================================================
# FAIR VALUE GAP
# ============================================================

def detect_fvg(df):

    if len(df) < 5:
        return "NONE", 0

    a = df.iloc[-3]
    b = df.iloc[-2]
    c = df.iloc[-1]

    # Bullish FVG
    if c["low"] > a["high"]:
        return "BULLISH FVG", 1

    # Bearish FVG
    if c["high"] < a["low"]:
        return "BEARISH FVG", -1

    return "NONE", 0


# ============================================================
# ORDER BLOCK ASAS
# ============================================================

def detect_order_block(df):

    if len(df) < 10:
        return "NONE", 0

    last = df.iloc[-1]
    previous = df.iloc[-2]

    body = abs(
        previous["close"] - previous["open"]
    )

    candle_range = (
        previous["high"] - previous["low"]
    )

    if candle_range == 0:
        return "NONE", 0

    # Bullish impulse selepas bearish candle
    if (
        previous["close"] < previous["open"]
        and last["close"] > previous["high"]
        and body / candle_range > 0.4
    ):
        return "BULLISH OB", 1

    # Bearish impulse selepas bullish candle
    if (
        previous["close"] > previous["open"]
        and last["close"] < previous["low"]
        and body / candle_range > 0.4
    ):
        return "BEARISH OB", -1

    return "NONE", 0


# ============================================================
# ANALYZE ONE TIMEFRAME
# ============================================================

def analyze_timeframe(df):

    if df is None or len(df) < 60:
        return None

    df = df.copy()

    df["ema20"] = calculate_ema(df, 20)
    df["ema50"] = calculate_ema(df, 50)
    df["rsi"] = calculate_rsi(df, 14)
    df["atr"] = calculate_atr(df, 14)

    last = df.iloc[-1]

    score = 0

    # EMA trend
    if last["ema20"] > last["ema50"]:
        score += 2
        trend = "BULLISH"
    elif last["ema20"] < last["ema50"]:
        score -= 2
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    # Price vs EMA
    if last["close"] > last["ema20"]:
        score += 1

    elif last["close"] < last["ema20"]:
        score -= 1

    # RSI
    if 50 < last["rsi"] < 70:
        score += 1

    elif 30 < last["rsi"] < 50:
        score -= 1

    elif last["rsi"] >= 70:
        score -= 1

    elif last["rsi"] <= 30:
        score += 1

    structure, structure_score = detect_structure(df)

    sweep, sweep_score = detect_liquidity_sweep(df)

    fvg, fvg_score = detect_fvg(df)

    ob, ob_score = detect_order_block(df)

    score += structure_score
    score += sweep_score
    score += fvg_score
    score += ob_score

    if score >= 3:
        direction = "BUY"

    elif score <= -3:
        direction = "SELL"

    else:
        direction = "WAIT"

    return {
        "trend": trend,
        "direction": direction,
        "score": score,
        "price": float(last["close"]),
        "ema20": float(last["ema20"]),
        "ema50": float(last["ema50"]),
        "rsi": float(last["rsi"]),
        "atr": float(last["atr"]),
        "structure": structure,
        "sweep": sweep,
        "fvg": fvg,
        "ob": ob
    }


# ============================================================
# MULTI TIMEFRAME ANALYSIS
# ============================================================

def analyze_market(symbol):

    base = get_candles(
        symbol,
        interval="5m",
        range_value="5d"
    )

    if base is None or base.empty:
        return None

    timeframes = [
        "M5",
        "M15",
        "H1",
        "H4"
    ]

    results = {}

    for tf in timeframes:

        df = resample_candles(
            base,
            tf
        )

        results[tf] = analyze_timeframe(df)

    return results


# ============================================================
# OVERALL SIGNAL
# ============================================================

def build_signal(symbol, name):

    analysis = analyze_market(symbol)

    if not analysis:
        return (
            f"❌ Tidak dapat mengambil data "
            f"{name} sekarang."
        )

    valid = [
        x for x in analysis.values()
        if x is not None
    ]

    if len(valid) < 4:

        return (
            f"⚠️ Data timeframe {name} "
            f"tidak lengkap."
        )

    total_score = sum(
        x["score"] for x in valid
    )

    bullish_tf = sum(
        1 for x in valid
        if x["direction"] == "BUY"
    )

    bearish_tf = sum(
        1 for x in valid
        if x["direction"] == "SELL"
    )

    if bullish_tf >= 3 and total_score > 0:

        overall = "BUY"
        emoji = "🟢"

    elif bearish_tf >= 3 and total_score < 0:

        overall = "SELL"
        emoji = "🔴"

    else:

        overall = "WAIT"
        emoji = "🟡"

    # Confidence
    max_score = len(valid) * 7

    confidence = abs(total_score) / max_score * 100

    confidence = max(
        0,
        min(
            95,
            confidence
        )
    )

    current = valid[0]["price"]

    # ATR M5 sebagai asas risk zone
    atr = valid[0]["atr"]

    if overall == "BUY":

        entry_low = current - atr * 0.25
        entry_high = current + atr * 0.10

        sl = current - atr * 1.5

        risk = current - sl

        tp1 = current + risk * 1.5
        tp2 = current + risk * 2.5

        status = (
            "WAIT FOR RETEST / "
            "CONFIRMATION"
        )

    elif overall == "SELL":

        entry_low = current - atr * 0.10
        entry_high = current + atr * 0.25

        sl = current + atr * 1.5

        risk = sl - current

        tp1 = current - risk * 1.5
        tp2 = current - risk * 2.5

        status = (
            "WAIT FOR RETEST / "
            "CONFIRMATION"
        )

    else:

        entry_low = current - atr * 0.25
        entry_high = current + atr * 0.25

        sl = None
        tp1 = None
        tp2 = None

        status = (
            "NO TRADE - WAIT "
            "FOR CLEAR STRUCTURE"
        )

    # ========================================================
    # FORMAT
    # ========================================================

    text = (
        f"📊 *{name} MARKET SIGNAL V2*\n\n"
        f"{emoji} *Overall: {overall}*\n"
        f"🔥 Confidence: `{confidence:.0f}%`\n"
        f"💰 Price: `${current:,.2f}`\n\n"
    )

    # Timeframes
    for tf in ["M5", "M15", "H1", "H4"]:

        item = analysis.get(tf)

        if item is None:

            text += (
                f"{tf}: ❌ No data\n"
            )

            continue

        if item["direction"] == "BUY":
            icon = "🟢"

        elif item["direction"] == "SELL":
            icon = "🔴"

        else:
            icon = "🟡"

        text += (
            f"{tf}: {icon} "
            f"{item['direction']} | "
            f"RSI `{item['rsi']:.1f}`\n"
        )

    # Structure
    m5 = analysis["M5"]

    text += (
        "\n📌 *Market Structure*\n"
        f"• Structure: `{m5['structure']}`\n"
        f"• Liquidity: `{m5['sweep']}`\n"
        f"• FVG: `{m5['fvg']}`\n"
        f"• Order Block: `{m5['ob']}`\n"
        f"• EMA20: `{m5['ema20']:,.2f}`\n"
        f"• EMA50: `{m5['ema50']:,.2f}`\n\n"
    )

    # Entry
    text += (
        "📍 *Entry Zone*\n"
        f"`{entry_low:,.2f} – "
        f"{entry_high:,.2f}`\n\n"
    )

    if overall != "WAIT":

        text += (
            f"🛑 *Stop Loss*\n"
            f"`${sl:,.2f}`\n\n"
            f"🎯 *TP1*\n"
            f"`${tp1:,.2f}`\n\n"
            f"🎯 *TP2*\n"
            f"`${tp2:,.2f}`\n\n"
        )

    text += (
        f"⚠️ *Status*\n"
        f"`{status}`\n\n"
        "_Analisis automatik berdasarkan data "
        "pasaran dan indikator teknikal. "
        "Bukan nasihat kewangan._"
    )

    return text


# ============================================================
# GOLD PRICE
# ============================================================

def get_gold_price():

    try:

        r = requests.get(
            "https://api.gold-api.com/price/XAU",
            timeout=10
        )

        r.raise_for_status()

        data = r.json()

        return float(
            data["price"]
        )

    except Exception as e:

        print(
            f"Gold price error: {e}"
        )

        return None


# ============================================================
# BTC PRICE
# ============================================================

def get_btc_price():

    try:

        r = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            timeout=10
        )

        r.raise_for_status()

        data = r.json()

        return float(
            data["data"]["amount"]
        )

    except Exception as e:

        print(
            f"BTC price error: {e}"
        )

        return None


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🤖 *Gold & BTC Signal Bot V2*\n\n"
        "📊 Market Structure + MTF Analysis\n\n"
        "*Commands:*\n"
        "/price – Harga semasa\n"
        "/signal gold – Analisis Gold\n"
        "/signal btc – Analisis BTC\n"
        "/news – News ringkas\n\n"
        "📌 Gold timeframe:\n"
        "M5 • M15 • H1 • H4"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /PRICE
# ============================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    gold = get_gold_price()

    btc = get_btc_price()

    text = "📈 *Harga Semasa*\n\n"

    if gold is not None:

        text += (
            f"🥇 Gold (XAU): "
            f"`${gold:,.2f}`\n"
        )

    else:

        text += (
            "🥇 Gold: "
            "Gagal ambil data\n"
        )

    if btc is not None:

        text += (
            f"₿ BTC: "
            f"`${btc:,.2f}`\n"
        )

    else:

        text += (
            "₿ BTC: "
            "Gagal ambil data\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /SIGNAL
# ============================================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "Contoh:\n\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    pair = (
        context.args[0]
        .lower()
        .strip()
    )

    if pair == "gold":

        await update.message.reply_text(
            "⏳ Menganalisis Gold "
            "M5/M15/H1/H4..."
        )

        msg = build_signal(
            "GC=F",
            "GOLD"
        )

    elif pair == "btc":

        await update.message.reply_text(
            "⏳ Menganalisis BTC "
            "M5/M15/H1/H4..."
        )

        msg = build_signal(
            "BTC-USD",
            "BTC"
        )

    else:

        msg = (
            "❌ Pair tidak disokong.\n\n"
            "Gunakan:\n"
            "/signal gold\n"
            "/signal btc"
        )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown"
    )


# ============================================================
# /NEWS
# ============================================================

async def news(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "📰 *News Monitor*\n\n"
        "🥇 Gold:\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• US yields\n"
        "• Inflation data\n\n"
        "₿ BTC:\n"
        "• ETF flows\n"
        "• US macro data\n"
        "• Liquidity\n"
        "• Market sentiment\n\n"
        "_News auto akan ditambah "
        "dalam versi seterusnya._"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TOKEN:

        print(
            "❌ BOT_TOKEN tidak dijumpai!"
        )

        print(
            "Variable Name: BOT_TOKEN"
        )

        return

    print(
        "✅ BOT_TOKEN berjaya dibaca!"
    )

    print(
        "🤖 Bot V2 sedang dimulakan..."
    )

    try:

        app = (
            Application
            .builder()
            .token(TOKEN)
            .build()
        )

        app.add_handler(
            CommandHandler(
                "start",
                start
            )
        )

        app.add_handler(
            CommandHandler(
                "price",
                price
            )
        )

        app.add_handler(
            CommandHandler(
                "signal",
                signal
            )
        )

        app.add_handler(
            CommandHandler(
                "news",
                news
            )
        )

        print(
            "🚀 Bot V2 sedang berjalan!"
        )

        print(
            "📡 Telegram polling aktif!"
        )

        app.run_polling(
            drop_pending_updates=True
        )

    except Exception as e:

        print(
            f"❌ BOT ERROR: {e}"
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
