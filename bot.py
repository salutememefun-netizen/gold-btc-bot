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
# GOLD & BTC SIGNAL BOT V5.3
# ============================================================
# FEATURES
# 15M + 1H
# EMA20 / EMA50
# RSI
# ATR
# ADX
# Market Structure
# Liquidity Sweep
# Candle Confirmation
# Support / Resistance
# Swing High / Swing Low
# Watch Zone
# Entry Trigger
# Entry Zone
# SL / TP
# No Auto Trading
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# ============================================================
# SYMBOLS
# ============================================================

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
                "User-Agent":
                "Mozilla/5.0"
            },
            timeout=20
        )

        if response.status_code != 200:

            logger.warning(
                f"{symbol} HTTP "
                f"{response.status_code}"
            )

            return []

        data = response.json()

        chart = data.get(
            "chart",
            {}
        )

        result = chart.get(
            "result"
        )

        if not result:
            return []

        result = result[0]

        timestamps = result.get(
            "timestamp",
            []
        )

        indicators = result.get(
            "indicators",
            {}
        )

        quote_list = indicators.get(
            "quote",
            []
        )

        if not quote_list:
            return []

        quote = quote_list[0]

        opens = quote.get(
            "open",
            []
        )

        highs = quote.get(
            "high",
            []
        )

        lows = quote.get(
            "low",
            []
        )

        closes = quote.get(
            "close",
            []
        )

        candles = []

        for i in range(
            len(timestamps)
        ):

            try:

                o = opens[i]
                h = highs[i]
                l = lows[i]
                c = closes[i]

                if (
                    o is None
                    or h is None
                    or l is None
                    or c is None
                ):
                    continue

                candles.append({
                    "time":
                        timestamps[i],

                    "open":
                        float(o),

                    "high":
                        float(h),

                    "low":
                        float(l),

                    "close":
                        float(c),
                })

            except (
                IndexError,
                TypeError,
                ValueError
            ):

                continue

        return candles

    except Exception as e:

        logger.error(
            f"Yahoo error "
            f"{symbol}: {e}"
        )

        return []


# ============================================================
# GET CANDLES WITH FALLBACK
# ============================================================

def get_candles(
    asset,
    interval,
    range_value
):

    symbols = SYMBOLS.get(
        asset,
        []
    )

    for symbol in symbols:

        candles = yahoo_candles(
            symbol,
            interval,
            range_value
        )

        if candles:

            logger.info(
                f"{asset} "
                f"{interval}: "
                f"{len(candles)} candles "
                f"from {symbol}"
            )

            return (
                candles,
                symbol
            )

    return [], None


# ============================================================
# LIVE PRICE
# ============================================================

def get_live_price(asset):

    candles, symbol = get_candles(
        asset,
        "1m",
        "1d"
    )

    if candles:

        return (
            candles[-1]["close"],
            symbol
        )

    # GOLD FALLBACK
    if asset == "gold":

        try:

            response = requests.get(
                "https://api.gold-api.com/price/XAU",
                timeout=15
            )

            if response.status_code == 200:

                data = response.json()

                price = data.get(
                    "price"
                )

                if price is not None:

                    return (
                        float(price),
                        "Gold-API"
                    )

        except Exception as e:

            logger.warning(
                f"Gold API error: {e}"
            )

    return None, None


# ============================================================
# EMA
# ============================================================

def ema(
    values,
    period
):

    if len(values) < period:

        return None

    multiplier = (
        2 / (period + 1)
    )

    value = (
        sum(
            values[:period]
        ) / period
    )

    for price in values[period:]:

        value = (
            (
                price - value
            )
            * multiplier
        ) + value

    return value


# ============================================================
# RSI
# ============================================================

def rsi(
    values,
    period=14
):

    if len(values) < period + 1:

        return None

    gains = []
    losses = []

    for i in range(
        1,
        len(values)
    ):

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

    for i in range(
        period,
        len(gains)
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss
                * (period - 1)
            )
            + losses[i]
        ) / period

    if avg_loss == 0:

        return 100

    rs = (
        avg_gain
        / avg_loss
    )

    return 100 - (
        100 / (1 + rs)
    )


# ============================================================
# ATR
# ============================================================

def atr(
    candles,
    period=14
):

    if len(candles) < period + 1:

        return None

    trs = []

    for i in range(
        1,
        len(candles)
    ):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"]
            - current["low"],

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
                value
                * (period - 1)
            )
            + tr
        ) / period

    return value


# ============================================================
# ADX
# ============================================================

def adx(
    candles,
    period=14
):

    if len(candles) < (
        period * 2 + 1
    ):

        return None

    trs = []
    plus_dm = []
    minus_dm = []

    for i in range(
        1,
        len(candles)
    ):

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
            current["high"]
            - current["low"],

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

        if (
            high_diff > low_diff
            and high_diff > 0
        ):

            plus_dm.append(
                high_diff
            )

        else:

            plus_dm.append(0)

        if (
            low_diff > high_diff
            and low_diff > 0
        ):

            minus_dm.append(
                low_diff
            )

        else:

            minus_dm.append(0)

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

    for i in range(
        period,
        len(trs)
    ):

        tr_avg = (
            (
                tr_avg
                * (period - 1)
            )
            + trs[i]
        ) / period

        plus_avg = (
            (
                plus_avg
                * (period - 1)
            )
            + plus_dm[i]
        ) / period

        minus_avg = (
            (
                minus_avg
                * (period - 1)
            )
            + minus_dm[i]
        ) / period

        if tr_avg == 0:

            continue

        plus_di = (
            100
            * plus_avg
            / tr_avg
        )

        minus_di = (
            100
            * minus_avg
            / tr_avg
        )

        total = (
            plus_di
            + minus_di
        )

        if total == 0:

            continue

        dx = (
            100
            * abs(
                plus_di
                - minus_di
            )
            / total
        )

        dx_values.append(dx)

    if len(dx_values) < period:

        return None

    return (
        sum(
            dx_values[-period:]
        )
        / period
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def market_structure(
    candles
):

    if len(candles) < 20:

        return "NEUTRAL"

    recent = candles[-20:]

    first = recent[:10]
    second = recent[10:]

    first_high = max(
        c["high"]
        for c in first
    )

    second_high = max(
        c["high"]
        for c in second
    )

    first_low = min(
        c["low"]
        for c in first
    )

    second_low = min(
        c["low"]
        for c in second
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

def swing_levels(
    candles,
    lookback=40
):

    if len(candles) < lookback:

        recent = candles

    else:

        recent = candles[
            -lookback:
        ]

    if not recent:

        return None, None

    swing_high = max(
        c["high"]
        for c in recent
    )

    swing_low = min(
        c["low"]
        for c in recent
    )

    return (
        swing_low,
        swing_high
    )


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def liquidity_sweep(
    candles
):

    if len(candles) < 10:

        return "NONE"

    previous = candles[-2]
    current = candles[-1]

    recent = candles[-10:-2]

    if not recent:

        return "NONE"

    previous_low = min(
        c["low"]
        for c in recent
    )

    previous_high = max(
        c["high"]
        for c in recent
    )

    # Bullish liquidity sweep
    # Harga cucuk low kemudian
    # candle tutup semula di atas low

    if (
        current["low"]
        < previous_low
        and current["close"]
        > previous_low
    ):

        return "BULLISH SWEEP"

    # Bearish liquidity sweep

    if (
        current["high"]
        > previous_high
        and current["close"]
        < previous_high
    ):

        return "BEARISH SWEEP"

    return "NONE"


# ============================================================
# CANDLE CONFIRMATION
# ============================================================

def candle_confirmation(
    candles
):

    if len(candles) < 3:

        return "NONE"

    current = candles[-1]
    previous = candles[-2]

    current_open = current["open"]
    current_close = current["close"]

    previous_open = previous["open"]
    previous_close = previous["close"]

    # Bullish engulfing

    bullish_engulfing = (
        current_close > current_open
        and previous_close < previous_open
        and current_close
        > previous_open
        and current_open
        < previous_close
    )

    # Bearish engulfing

    bearish_engulfing = (
        current_close < current_open
        and previous_close > previous_open
        and current_close
        < previous_open
        and current_open
        > previous_close
    )

    if bullish_engulfing:

        return "BULLISH ENGULFING"

    if bearish_engulfing:

        return "BEARISH ENGULFING"

    # Normal bullish candle

    if (
        current_close > current_open
    ):

        body = abs(
            current_close
            - current_open
        )

        candle_range = (
            current["high"]
            - current["low"]
        )

        if (
            candle_range > 0
            and body
            / candle_range >= 0.60
        ):

            return "BULLISH CANDLE"

    # Normal bearish candle

    if (
        current_close < current_open
    ):

        body = abs(
            current_close
            - current_open
        )

        candle_range = (
            current["high"]
            - current["low"]
        )

        if (
            candle_range > 0
            and body
            / candle_range >= 0.60
        ):

            return "BEARISH CANDLE"

    return "NONE"


# ============================================================
# ANALYZE
# ============================================================

def analyze_asset(
    asset
):

    candles_15m, source_15m = (
        get_candles(
            asset,
            "15m",
            "5d"
        )
    )

    candles_1h, source_1h = (
        get_candles(
            asset,
            "1h",
            "1mo"
        )
    )

    if len(candles_15m) < 60:

        logger.warning(
            f"{asset}: only "
            f"{len(candles_15m)} "
            f"15M candles"
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

    structure = (
        market_structure(
            candles_15m
        )
    )

    swing_low, swing_high = (
        swing_levels(
            candles_15m,
            40
        )
    )

    sweep = (
        liquidity_sweep(
            candles_15m
        )
    )

    candle = (
        candle_confirmation(
            candles_15m
        )
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

            if (
                h1_ema20
                > h1_ema50
            ):

                h1_trend = "BULLISH"

            elif (
                h1_ema20
                < h1_ema50
            ):

                h1_trend = "BEARISH"

    # ========================================================
    # SCORE
    # ========================================================

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    # EMA

    if (
        ema20 is not None
        and ema50 is not None
    ):

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

        if (
            50 <= rsi_value <= 70
        ):

            buy_score += 15

            buy_reasons.append(
                "RSI menyokong "
                "momentum bullish"
            )

        elif (
            30 <= rsi_value < 50
        ):

            sell_score += 15

            sell_reasons.append(
                "RSI menyokong "
                "momentum bearish"
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

    if (
        adx_value is not None
        and adx_value >= 25
    ):

        if buy_score > sell_score:

            buy_score += 15

            buy_reasons.append(
                "ADX menunjukkan "
                "trend kuat"
            )

        elif sell_score > buy_score:

            sell_score += 15

            sell_reasons.append(
                "ADX menunjukkan "
                "trend kuat"
            )

    # ========================================================
    # BASE DIRECTION
    # ========================================================

    if (
        buy_score >= 55
        and buy_score > sell_score
    ):

        base_direction = "BUY"

    elif (
        sell_score >= 55
        and sell_score > buy_score
    ):

        base_direction = "SELL"

    else:

        base_direction = "WAIT"

    # ========================================================
    # ENTRY TRIGGER
    # ========================================================
    #
    # BUY trigger:
    # 1. Base direction BUY
    # 2. Bullish liquidity sweep
    # 3. Bullish candle confirmation
    #
    # SELL trigger:
    # 1. Base direction SELL
    # 2. Bearish liquidity sweep
    # 3. Bearish candle confirmation
    #
    # Jika belum lengkap = WAIT
    # ========================================================

    buy_trigger = (
        base_direction == "BUY"
        and sweep == "BULLISH SWEEP"
        and candle in (
            "BULLISH ENGULFING",
            "BULLISH CANDLE"
        )
    )

    sell_trigger = (
        base_direction == "SELL"
        and sweep == "BEARISH SWEEP"
        and candle in (
            "BEARISH ENGULFING",
            "BEARISH CANDLE"
        )
    )

    if buy_trigger:

        direction = "BUY"

        confidence = min(
            buy_score + 15,
            100
        )

        reasons = list(
            buy_reasons
        )

        reasons.append(
            "Bullish liquidity sweep"
        )

        reasons.append(
            candle
        )

        trigger = (
            "BUY TRIGGER CONFIRMED"
        )

    elif sell_trigger:

        direction = "SELL"

        confidence = min(
            sell_score + 15,
            100
        )

        reasons = list(
            sell_reasons
        )

        reasons.append(
            "Bearish liquidity sweep"
        )

        reasons.append(
            candle
        )

        trigger = (
            "SELL TRIGGER CONFIRMED"
        )

    else:

        direction = "WAIT"

        confidence = max(
            buy_score,
            sell_score
        )

        reasons = [
            "Entry trigger belum lengkap"
        ]

        if base_direction == "BUY":

            reasons.append(
                "Bias BUY tetapi "
                "tunggu bullish sweep + "
                "candle confirmation"
            )

        elif base_direction == "SELL":

            reasons.append(
                "Bias SELL tetapi "
                "tunggu bearish sweep + "
                "candle confirmation"
            )

        else:

            reasons.append(
                "Trend belum cukup kuat"
            )

        trigger = (
            "WAIT FOR ENTRY TRIGGER"
        )

    # ========================================================
    # ATR
    # ========================================================

    if (
        atr_value is None
        or atr_value <= 0
    ):

        atr_value = (
            price * 0.005
        )

    # ========================================================
    # WATCH ZONE
    # ========================================================

    zone_size = (
        atr_value * 0.25
    )

    watch_low = (
        price - zone_size
    )

    watch_high = (
        price + zone_size
    )

    # ========================================================
    # ENTRY / SL / TP
    # ========================================================

    if direction == "BUY":

        entry_low = watch_low
        entry_high = watch_high

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

        entry_low = watch_low
        entry_high = watch_high

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

        entry_low = watch_low
        entry_high = watch_high

        sl = None
        tp1 = None
        tp2 = None

    return {

        "price":
            price,

        "direction":
            direction,

        "base_direction":
            base_direction,

        "confidence":
            confidence,

        "buy_score":
            buy_score,

        "sell_score":
            sell_score,

        "structure":
            structure,

        "h1_trend":
            h1_trend,

        "rsi":
            rsi_value,

        "adx":
            adx_value,

        "atr":
            atr_value,

        "sweep":
            sweep,

        "candle":
            candle,

        "trigger":
            trigger,

        "swing_low":
            swing_low,

        "swing_high":
            swing_high,

        "watch_low":
            watch_low,

        "watch_high":
            watch_high,

        "entry_low":
            entry_low,

        "entry_high":
            entry_high,

        "sl":
            sl,

        "tp1":
            tp1,

        "tp2":
            tp2,

        "reasons":
            reasons,

        "source_15m":
            source_15m,

        "source_1h":
            source_1h,
    }


# ============================================================
# FORMAT SIGNAL
# ============================================================

def format_signal(
    asset,
    result
):

    if result is None:

        return (
            "❌ *DATA CANDLE GAGAL*\n\n"
            "15M candle tidak mencukupi.\n"
            "Sumber fallback akan dicuba "
            "secara automatik.\n\n"
            "🔄 Cuba semula."
        )

    if asset == "gold":

        name = "GOLD (XAUUSD)"
        emoji = "🥇"

    else:

        name = "BTC"
        emoji = "₿"

    price = result["price"]
    direction = result["direction"]

    confidence = result[
        "confidence"
    ]

    rsi_value = result["rsi"]
    adx_value = result["adx"]

    # ========================================================
    # HEADER
    # ========================================================

    message = (
        f"{emoji} *{name} SIGNAL V5.3*\n\n"

        f"💰 Harga: "
        f"`${price:,.2f}`\n\n"
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
        f"💯 Confidence: "
        f"`{confidence}%`\n"

        f"📐 Structure: "
        f"`{result['structure']}`\n"

        f"🕐 1H Trend: "
        f"`{result['h1_trend']}`\n"

        f"📊 RSI: "
        f"`{rsi_value:.1f}`\n"

        f"📈 ADX: "
        f"`{adx_value:.1f}`\n\n"
    )

    # ========================================================
    # LIQUIDITY
    # ========================================================

    message += (
        "💧 *LIQUIDITY*\n"
        f"`{result['sweep']}`\n\n"
    )

    # ========================================================
    # CANDLE
    # ========================================================

    message += (
        "🕯 *CANDLE CONFIRMATION*\n"
        f"`{result['candle']}`\n\n"
    )

    # ========================================================
    # ENTRY TRIGGER
    # ========================================================

    if direction == "BUY":

        message += (
            "🚀 *ENTRY TRIGGER*\n"
            "🟢 BUY TRIGGER CONFIRMED\n\n"
        )

    elif direction == "SELL":

        message += (
            "🚀 *ENTRY TRIGGER*\n"
            "🔴 SELL TRIGGER CONFIRMED\n\n"
        )

    else:

        message += (
            "⏳ *ENTRY TRIGGER*\n"
            "🟡 WAIT FOR ENTRY TRIGGER\n\n"
        )

    # ========================================================
    # WATCH ZONE
    # ========================================================

    message += (
        "🟡 *WATCH ZONE*\n"
        f"`{result['watch_low']:,.2f}"
        f" – "
        f"{result['watch_high']:,.2f}`\n\n"
    )

    # ========================================================
    # SWINGS
    # ========================================================

    message += (
        "📉 *SWING LOW*\n"
        f"`{result['swing_low']:,.2f}`\n\n"

        "📈 *SWING HIGH*\n"
        f"`{result['swing_high']:,.2f}`\n\n"
    )

    # ========================================================
    # SUPPORT / RESISTANCE
    # ========================================================

    message += (
        "🧱 *SUPPORT / RESISTANCE*\n"
        f"Support: "
        f"`{result['swing_low']:,.2f}`\n"

        f"Resistance: "
        f"`{result['swing_high']:,.2f}`\n\n"
    )

    # ========================================================
    # ENTRY / SL / TP
    # ========================================================

    if direction != "WAIT":

        message += (
            "🎯 *ENTRY ZONE*\n"
            f"`{result['entry_low']:,.2f}"
            f" – "
            f"{result['entry_high']:,.2f}`\n\n"

            "🛑 *STOP LOSS*\n"
            f"`{result['sl']:,.2f}`\n\n"

            "🎯 *TP1*\n"
            f"`{result['tp1']:,.2f}`\n\n"

            "🎯 *TP2*\n"
            f"`{result['tp2']:,.2f}`\n\n"
        )

    # ========================================================
    # ANALYSIS
    # ========================================================

    message += (
        "🧠 *ANALYSIS*\n"
    )

    for reason in result[
        "reasons"
    ]:

        message += (
            f"• {reason}\n"
        )

    # ========================================================
    # SOURCE
    # ========================================================

    message += (
        "\n📡 *DATA SOURCE*\n"

        f"15M: "
        f"`{result['source_15m']}`\n"

        f"1H: "
        f"`{result['source_1h']}`\n\n"

        "⚠️ Technical signal sahaja. "
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
        "🤖 *GOLD & BTC SIGNAL BOT V5.3*\n\n"

        "📌 *COMMANDS*\n\n"

        "/price\n"
        "➡️ Harga Gold & BTC\n\n"

        "/signal gold\n"
        "➡️ Signal Gold\n\n"

        "/signal btc\n"
        "➡️ Signal BTC\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 Technical Engine V5.3\n"
        "📊 15M + 1H\n"
        "📐 Market Structure\n"
        "📈 EMA / RSI / ADX / ATR\n"
        "💧 Liquidity Sweep\n"
        "🕯️ Candle Confirmation\n"
        "🎯 Entry Trigger\n"
        "📍 Watch / Entry Zone\n"
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

    gold, gold_source = (
        get_live_price("gold")
    )

    btc, btc_source = (
        get_live_price("btc")
    )

    text = (
        "📈 *HARGA SEMASA V5.3*\n\n"
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

    asset = (
        context.args[0]
        .lower()
    )

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

    status = (
        await update.message.reply_text(
            "🧠 *SIGNAL V5.3*\n\n"
            "📡 Mengambil candle...\n"
            "📊 15M + 1H\n"
            "💧 Checking liquidity...\n"
            "🕯️ Checking candle...\n"
            "🎯 Checking entry trigger...\n"
            "⏳ Sila tunggu..."
        )
    )

    try:

        result = analyze_asset(
            asset
        )

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
        "📰 *NEWS MONITOR V5.3*\n\n"

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

        "⚠️ News engine belum "
        "mengambil berita live."
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
    print(
        "=========================================="
    )

    print(
        "🤖 GOLD & BTC SIGNAL BOT V5.3"
    )

    print(
        "=========================================="
    )

    if not TOKEN:

        print("")
        print(
            "❌ BOT_TOKEN TIDAK DIJUMPAI"
        )

        print("")

        print(
            "Pastikan Railway Variable:"
        )

        print(
            "BOT_TOKEN = token BotFather"
        )

        print("")

        return

    print(
        "✅ BOT_TOKEN berjaya dibaca!"
    )

    print(
        "🤖 Starting V5.3..."
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
            "🚀 V5.3 BOT AKTIF!"
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
            "💧 Liquidity sweep: ON"
        )

        print(
            "🕯️ Candle confirmation: ON"
        )

        print(
            "🎯 Entry trigger: ON"
        )

        print(
            "=========================================="
        )

        application.run_polling(
            drop_pending_updates=True
        )

    except Exception as e:

        print("")

        print(
            "❌ BOT ERROR"
        )

        print(
            str(e)
        )

        print("")

        logger.exception(
            "Fatal bot error"
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
