import os
import logging
import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# GOLD & BTC SIGNAL BOT V5.2
# Technical signal only - NO AUTO TRADING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

SYMBOLS = {
    "gold": ["GC=F", "XAUUSD=X"],
    "btc": ["BTC-USD"],
}


# ============================================================
# YAHOO CANDLES
# ============================================================

def yahoo_candles(symbol, interval="15m", range_value="5d"):

    url = (
        "https://query1.finance.yahoo.com/"
        f"v8/finance/chart/{symbol}"
    )

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

        if response.status_code != 200:
            logger.warning(
                f"{symbol} HTTP {response.status_code}"
            )
            return []

        data = response.json()

        result = data.get("chart", {}).get("result")

        if not result:
            return []

        result = result[0]

        timestamps = result.get("timestamp", [])

        quote_list = (
            result
            .get("indicators", {})
            .get("quote", [])
        )

        if not quote_list:
            return []

        quote = quote_list[0]

        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])

        candles = []

        for i in range(len(timestamps)):

            try:

                o = opens[i]
                h = highs[i]
                l = lows[i]
                c = closes[i]

                if None in (o, h, l, c):
                    continue

                candles.append({
                    "time": timestamps[i],
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c)
                })

            except Exception:
                continue

        return candles

    except Exception as e:

        logger.error(
            f"Yahoo error {symbol}: {e}"
        )

        return []


# ============================================================
# CANDLE FALLBACK
# ============================================================

def get_candles(asset, interval, range_value):

    for symbol in SYMBOLS.get(asset, []):

        candles = yahoo_candles(
            symbol,
            interval,
            range_value
        )

        if candles:

            logger.info(
                f"{asset} {interval}: "
                f"{len(candles)} candles "
                f"source={symbol}"
            )

            return candles, symbol

    return [], None


# ============================================================
# LIVE PRICE
# ============================================================

def get_live_price(asset):

    candles, source = get_candles(
        asset,
        "1m",
        "1d"
    )

    if candles:

        return candles[-1]["close"], source

    # Gold API fallback
    if asset == "gold":

        try:

            response = requests.get(
                "https://api.gold-api.com/price/XAU",
                timeout=15
            )

            if response.status_code == 200:

                data = response.json()

                price = data.get("price")

                if price is not None:

                    return float(price), "Gold-API"

        except Exception as e:

            logger.warning(
                f"Gold API error: {e}"
            )

    return None, None


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
            (price - value)
            * multiplier
        ) + value

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

        change = (
            values[i]
            - values[i - 1]
        )

        gains.append(
            max(change, 0)
        )

        losses.append(
            max(-change, 0)
        )

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for i in range(period, len(gains)):

        avg_gain = (
            (
                avg_gain * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss * (period - 1)
            )
            + losses[i]
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

    value = (
        sum(trs[:period])
        / period
    )

    for tr in trs[period:]:

        value = (
            (
                value * (period - 1)
            )
            + tr
        ) / period

    return value


# ============================================================
# ADX
# ============================================================

def adx(candles, period=14):

    if len(candles) < period * 2 + 1:
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

    tr_avg = (
        sum(trs[:period])
        / period
    )

    plus_avg = (
        sum(plus_dm[:period])
        / period
    )

    minus_avg = (
        sum(minus_dm[:period])
        / period
    )

    dx_values = []

    for i in range(period, len(trs)):

        tr_avg = (
            (
                tr_avg * (period - 1)
            )
            + trs[i]
        ) / period

        plus_avg = (
            (
                plus_avg * (period - 1)
            )
            + plus_dm[i]
        ) / period

        minus_avg = (
            (
                minus_avg * (period - 1)
            )
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

        total = plus_di + minus_di

        if total == 0:
            continue

        dx = (
            100
            * abs(plus_di - minus_di)
            / total
        )

        dx_values.append(dx)

    if len(dx_values) < period:
        return None

    return (
        sum(dx_values[-period:])
        / period
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def market_structure(candles):

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
# SWING LEVELS
# ============================================================

def swing_levels(candles, lookback=40):

    if len(candles) < lookback:
        recent = candles
    else:
        recent = candles[-lookback:]

    if not recent:
        return None, None

    swing_high = max(
        c["high"] for c in recent
    )

    swing_low = min(
        c["low"] for c in recent
    )

    return swing_low, swing_high


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def support_resistance(candles, lookback=40):

    if not candles:
        return None, None

    recent = candles[-lookback:]

    support = min(
        c["low"] for c in recent
    )

    resistance = max(
        c["high"] for c in recent
    )

    return support, resistance


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def liquidity_sweep(candles, lookback=10):

    if len(candles) < lookback + 2:
        return "NONE"

    previous = candles[
        -(lookback + 1):-1
    ]

    current = candles[-1]

    previous_high = max(
        c["high"] for c in previous
    )

    previous_low = min(
        c["low"] for c in previous
    )

    # Sweep low kemudian tutup kembali atas low
    if (
        current["low"] < previous_low
        and current["close"] > previous_low
    ):
        return "BULLISH_SWEEP"

    # Sweep high kemudian tutup kembali bawah high
    if (
        current["high"] > previous_high
        and current["close"] < previous_high
    ):
        return "BEARISH_SWEEP"

    return "NONE"


# ============================================================
# CANDLE CONFIRMATION
# ============================================================

def candle_confirmation(candles):

    if len(candles) < 3:
        return "NONE"

    current = candles[-1]
    previous = candles[-2]

    # Bullish engulfing
    bullish = (
        previous["close"] < previous["open"]
        and current["close"] > current["open"]
        and current["close"] >= previous["open"]
        and current["open"] <= previous["close"]
    )

    if bullish:
        return "BULLISH_ENGULFING"

    # Bearish engulfing
    bearish = (
        previous["close"] > previous["open"]
        and current["close"] < current["open"]
        and current["open"] >= previous["close"]
        and current["close"] <= previous["open"]
    )

    if bearish:
        return "BEARISH_ENGULFING"

    # Strong bullish close
    candle_range = (
        current["high"]
        - current["low"]
    )

    if candle_range > 0:

        close_position = (
            current["close"]
            - current["low"]
        ) / candle_range

        if (
            current["close"] > current["open"]
            and close_position >= 0.70
        ):
            return "BULLISH_CLOSE"

        if (
            current["close"] < current["open"]
            and close_position <= 0.30
        ):
            return "BEARISH_CLOSE"

    return "NONE"


# ============================================================
# ZONE CALCULATION
# ============================================================

def calculate_zone(
    price,
    atr_value,
    direction,
    support,
    resistance,
    sweep
):

    zone_size = atr_value * 0.25

    # BUY
    if direction == "BUY":

        if (
            support is not None
            and support < price
            and price - support <= atr_value * 1.5
        ):

            center = support

        elif sweep == "BULLISH_SWEEP":

            center = price - (
                atr_value * 0.20
            )

        else:

            center = price

        return (
            center - zone_size,
            center + zone_size
        )

    # SELL
    if direction == "SELL":

        if (
            resistance is not None
            and resistance > price
            and resistance - price <= atr_value * 1.5
        ):

            center = resistance

        elif sweep == "BEARISH_SWEEP":

            center = price + (
                atr_value * 0.20
            )

        else:

            center = price

        return (
            center - zone_size,
            center + zone_size
        )

    # WAIT
    return (
        price - zone_size,
        price + zone_size
    )


# ============================================================
# ANALYZE
# ============================================================

def analyze_asset(asset):

    candles_15m, source_15m = get_candles(
        asset,
        "15m",
        "5d"
    )

    candles_1h, source_1h = get_candles(
        asset,
        "1h",
        "1mo"
    )

    if len(candles_15m) < 60:

        logger.warning(
            f"{asset}: "
            f"{len(candles_15m)} 15M candles"
        )

        return None

    closes = [
        c["close"]
        for c in candles_15m
    ]

    price = closes[-1]

    ema20 = ema(
        closes,
        20
    )

    ema50 = ema(
        closes,
        50
    )

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

    swing_low, swing_high = swing_levels(
        candles_15m,
        40
    )

    support, resistance = support_resistance(
        candles_15m,
        40
    )

    sweep = liquidity_sweep(
        candles_15m,
        10
    )

    confirmation = candle_confirmation(
        candles_15m
    )

    # ========================================================
    # H1 TREND
    # ========================================================

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

    # ========================================================
    # SCORING
    # ========================================================

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    # EMA
    if ema20 is not None and ema50 is not None:

        if ema20 > ema50:

            buy_score += 20

            buy_reasons.append(
                "EMA20 di atas EMA50"
            )

        elif ema20 < ema50:

            sell_score += 20

            sell_reasons.append(
                "EMA20 di bawah EMA50"
            )

    # RSI
    if rsi_value is not None:

        if 50 <= rsi_value <= 68:

            buy_score += 15

            buy_reasons.append(
                "RSI menyokong momentum bullish"
            )

        elif 32 <= rsi_value < 50:

            sell_score += 15

            sell_reasons.append(
                "RSI menyokong momentum bearish"
            )

        elif rsi_value > 70:

            sell_reasons.append(
                "RSI tinggi - risiko pullback"
            )

        elif rsi_value < 30:

            buy_reasons.append(
                "RSI rendah - potensi rebound"
            )

    # Structure
    if structure == "BULLISH":

        buy_score += 20

        buy_reasons.append(
            "Market structure bullish"
        )

    elif structure == "BEARISH":

        sell_score += 20

        sell_reasons.append(
            "Market structure bearish"
        )

    # H1
    if h1_trend == "BULLISH":

        buy_score += 20

        buy_reasons.append(
            "Trend 1H bullish"
        )

    elif h1_trend == "BEARISH":

        sell_score += 20

        sell_reasons.append(
            "Trend 1H bearish"
        )

    # ADX
    if adx_value is not None:

        if adx_value >= 25:

            if buy_score > sell_score:

                buy_score += 15

                buy_reasons.append(
                    "ADX menunjukkan trend kuat"
                )

            elif sell_score > buy_score:

                sell_score += 15

                sell_reasons.append(
                    "ADX menunjukkan trend kuat"
                )

    # Liquidity sweep
    if sweep == "BULLISH_SWEEP":

        buy_score += 10

        buy_reasons.append(
            "Bullish liquidity sweep"
        )

    elif sweep == "BEARISH_SWEEP":

        sell_score += 10

        sell_reasons.append(
            "Bearish liquidity sweep"
        )

    # Candle confirmation
    if confirmation in (
        "BULLISH_ENGULFING",
        "BULLISH_CLOSE"
    ):

        buy_score += 10

        buy_reasons.append(
            "Candle confirmation bullish"
        )

    elif confirmation in (
        "BEARISH_ENGULFING",
        "BEARISH_CLOSE"
    ):

        sell_score += 10

        sell_reasons.append(
            "Candle confirmation bearish"
        )

    # ========================================================
    # SIGNAL LOGIC
    # ========================================================

    # Minimum score 60 supaya tidak terlalu mudah
    if (
        buy_score >= 60
        and buy_score > sell_score
    ):

        direction = "BUY"
        confidence = min(buy_score, 100)
        reasons = buy_reasons

    elif (
        sell_score >= 60
        and sell_score > buy_score
    ):

        direction = "SELL"
        confidence = min(sell_score, 100)
        reasons = sell_reasons

    else:

        direction = "WAIT"

        confidence = min(
            max(
                buy_score,
                sell_score
            ),
            100
        )

        reasons = [
            "Confirmation belum mencukupi"
        ]

    # ========================================================
    # ATR
    # ========================================================

    if (
        atr_value is None
        or atr_value <= 0
    ):

        atr_value = price * 0.005

    # ========================================================
    # ENTRY ZONE
    # ========================================================

    entry_low, entry_high = calculate_zone(
        price,
        atr_value,
        direction,
        support,
        resistance,
        sweep
    )

    # ========================================================
    # SL / TP
    # ========================================================

    if direction == "BUY":

        sl = entry_low - (
            atr_value * 0.80
        )

        risk = (
            entry_high - sl
        )

        tp1 = entry_high + (
            risk * 1.0
        )

        tp2 = entry_high + (
            risk * 2.0
        )

    elif direction == "SELL":

        sl = entry_high + (
            atr_value * 0.80
        )

        risk = (
            sl - entry_low
        )

        tp1 = entry_low - (
            risk * 1.0
        )

        tp2 = entry_low - (
            risk * 2.0
        )

    else:

        sl = None
        tp1 = None
        tp2 = None

    # ========================================================
    # RISK / REWARD
    # ========================================================

    if direction == "BUY":

        risk = entry_high - sl
        reward = tp2 - entry_high

    elif direction == "SELL":

        risk = sl - entry_low
        reward = entry_low - tp2

    else:

        risk = None
        reward = None

    if (
        risk is not None
        and risk > 0
        and reward is not None
    ):

        rr = reward / risk

    else:

        rr = None

    return {
        "price": price,
        "direction": direction,
        "confidence": confidence,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "structure": structure,
        "h1_trend": h1_trend,
        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "support": support,
        "resistance": resistance,
        "sweep": sweep,
        "confirmation": confirmation,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "rr": rr,
        "reasons": reasons,
        "source_15m": source_15m,
        "source_1h": source_1h,
    }


# ============================================================
# FORMAT SIGNAL
# ============================================================

def format_signal(asset, result):

    if result is None:

        return (
            "❌ *DATA CANDLE GAGAL*\n\n"
            "15M candle tidak mencukupi.\n"
            "Cuba semula selepas beberapa saat."
        )

    if asset == "gold":

        name = "GOLD (XAUUSD)"
        emoji = "🥇"

    else:

        name = "BTC"
        emoji = "₿"

    price = result["price"]

    direction = result["direction"]

    confidence = result["confidence"]

    rsi_value = result["rsi"]
    adx_value = result["adx"]

    # ========================================================
    # HEADER
    # ========================================================

    message = (
        f"{emoji} *{name} SIGNAL V5.2*\n\n"
        f"💰 Harga: `${price:,.2f}`\n\n"
    )

    if direction == "BUY":

        message += (
            "🟢 *SIGNAL: BUY*\n"
            "📈 Bias bullish\n\n"
        )

    elif direction == "SELL":

        message += (
            "🔴 *SIGNAL: SELL*\n"
            "📉 Bias bearish\n\n"
        )

    else:

        message += (
            "🟡 *SIGNAL: WAIT*\n"
            "⏳ Confirmation belum cukup\n\n"
        )

    # ========================================================
    # METRICS
    # ========================================================

    message += (
        f"💯 Confidence: `{confidence}%`\n"
        f"📐 Structure: `{result['structure']}`\n"
        f"🕐 1H Trend: `{result['h1_trend']}`\n"
        f"📊 RSI: `{rsi_value:.1f}`\n"
        f"📈 ADX: `{adx_value:.1f}`\n\n"
    )

    # ========================================================
    # LIQUIDITY
    # ========================================================

    sweep_text = result["sweep"]

    if sweep_text == "BULLISH_SWEEP":
        sweep_display = "🟢 Bullish sweep"

    elif sweep_text == "BEARISH_SWEEP":
        sweep_display = "🔴 Bearish sweep"

    else:
        sweep_display = "⚪ Tiada sweep"

    message += (
        "💧 *LIQUIDITY*\n"
        f"{sweep_display}\n\n"
    )

    # ========================================================
    # CONFIRMATION
    # ========================================================

    confirmation = result["confirmation"]

    if confirmation == "BULLISH_ENGULFING":
        confirmation_display = "🟢 Bullish engulfing"

    elif confirmation == "BEARISH_ENGULFING":
        confirmation_display = "🔴 Bearish engulfing"

    elif confirmation == "BULLISH_CLOSE":
        confirmation_display = "🟢 Bullish candle close"

    elif confirmation == "BEARISH_CLOSE":
        confirmation_display = "🔴 Bearish candle close"

    else:
        confirmation_display = "⚪ Tiada confirmation"

    message += (
        "🕯 *CANDLE CONFIRMATION*\n"
        f"{confirmation_display}\n\n"
    )

    # ========================================================
    # ZONE
    # ========================================================

    if direction == "WAIT":

        message += (
            "🟡 *WATCH ZONE*\n"
            f"`{result['entry_low']:,.2f} "
            f"– "
            f"{result['entry_high']:,.2f}`\n\n"
        )

    else:

        message += (
            "🟢 *ENTRY ZONE*\n"
            f"`{result['entry_low']:,.2f} "
            f"– "
            f"{result['entry_high']:,.2f}`\n\n"
        )

        message += (
            "🛑 *STOP LOSS*\n"
            f"`{result['sl']:,.2f}`\n\n"

            "🎯 *TP1*\n"
            f"`{result['tp1']:,.2f}`\n\n"

            "🎯 *TP2*\n"
            f"`{result['tp2']:,.2f}`\n\n"
        )

        if result["rr"] is not None:

            message += (
                "⚖️ *Risk / Reward*\n"
                f"`1 : {result['rr']:.2f}`\n\n"
            )

    # ========================================================
    # SWINGS
    # ========================================================

    message += (
        "📉 *Swing Low*\n"
        f"`{result['swing_low']:,.2f}`\n\n"

        "📈 *Swing High*\n"
        f"`{result['swing_high']:,.2f}`\n\n"
    )

    # ========================================================
    # SUPPORT RESISTANCE
    # ========================================================

    message += (
        "🧱 *SUPPORT / RESISTANCE*\n"
        f"Support: `{result['support']:,.2f}`\n"
        f"Resistance: `{result['resistance']:,.2f}`\n\n"
    )

    # ========================================================
    # ANALYSIS
    # ========================================================

    message += "🧠 *ANALYSIS*\n"

    for reason in result["reasons"]:

        message += (
            f"• {reason}\n"
        )

    # ========================================================
    # SOURCE
    # ========================================================

    message += (
        "\n📡 *DATA SOURCE*\n"
        f"15M: `{result['source_15m']}`\n"
        f"1H: `{result['source_1h']}`\n\n"

        "⚠️ Technical signal sahaja.\n"
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
        "🤖 *GOLD & BTC SIGNAL BOT V5.2*\n\n"

        "📌 *COMMANDS*\n\n"

        "/price\n"
        "➡️ Harga semasa\n\n"

        "/signal gold\n"
        "➡️ Analisis Gold\n\n"

        "/signal btc\n"
        "➡️ Analisis BTC\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 Technical Engine V5.2\n"
        "📊 15M + 1H\n"
        "📐 Market Structure\n"
        "💧 Liquidity Sweep\n"
        "🧱 Support / Resistance\n"
        "🕯 Candle Confirmation\n"
        "🎯 Entry Zone / SL / TP\n"
        "⚖️ Risk / Reward\n"
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

    gold, gold_source = get_live_price("gold")

    btc, btc_source = get_live_price("btc")

    text = (
        "📈 *HARGA SEMASA V5.2*\n\n"
    )

    if gold is not None:

        text += (
            "🥇 *Gold XAUUSD*\n"
            f"`${gold:,.2f}`\n"
            f"Source: `{gold_source}`\n\n"
        )

    else:

        text += (
            "🥇 Gold: ❌ Gagal\n\n"
        )

    if btc is not None:

        text += (
            "₿ *Bitcoin BTC*\n"
            f"`${btc:,.2f}`\n"
            f"Source: `{btc_source}`\n"
        )

    else:

        text += (
            "₿ BTC: ❌ Gagal\n"
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

    if asset not in (
        "gold",
        "btc"
    ):

        await update.message.reply_text(
            "❌ Asset tidak disokong.\n\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    status = await update.message.reply_text(
        "🧠 *SIGNAL V5.2*\n\n"
        "📡 Mengambil candle...\n"
        "📊 15M + 1H\n"
        "💧 Checking liquidity...\n"
        "🧱 Checking S/R...\n"
        "🕯 Checking confirmation...\n"
        "⏳ Sila tunggu..."
    )

    try:

        result = analyze_asset(asset)

        message = format_signal(
            asset,
            result
        )

        await status.edit_text(
            message,
            parse_mode="Markdown"
        )

    except Exception as e:

        logger.exception(
            "Signal error"
        )

        await status.edit_text(
            "❌ *SIGNAL ERROR*\n\n"
            f"`{str(e)}`",
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
        "📰 *NEWS MONITOR V5.2*\n\n"

        "🥇 *GOLD*\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• US CPI\n"
        "• NFP\n"
        "• Interest Rate\n\n"

        "₿ *BITCOIN*\n"
        "• ETF Flow\n"
        "• Funding Rate\n"
        "• BTC Dominance\n"
        "• US Macro Data\n\n"

        "⚠️ News live belum diaktifkan."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# ERROR HANDLER
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
    print("🤖 GOLD & BTC SIGNAL BOT V5.2")
    print("==========================================")

    if not TOKEN:

        print("")
        print("❌ BOT_TOKEN TIDAK DIJUMPAI")
        print("")

        return

    print(
        "✅ BOT_TOKEN berjaya dibaca!"
    )

    print(
        "🤖 Starting V5.2..."
    )

    try:

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

        print(
            "🚀 V5.2 BOT AKTIF!"
        )

        print(
            "📡 Telegram polling aktif!"
        )

        print(
            "🥇 Gold fallback: GC=F"
        )

        print(
            "₿ BTC: BTC-USD"
        )

        print(
            "📊 Timeframe: 15M + 1H"
        )

        print(
            "💧 Liquidity Sweep aktif"
        )

        print(
            "🧱 Support/Resistance aktif"
        )

        print(
            "🕯 Candle Confirmation aktif"
        )

        print(
            "🎯 Entry Zone aktif"
        )

        print(
            "🚫 Auto trading: OFF"
        )

        print(
            "=========================================="
        )

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
