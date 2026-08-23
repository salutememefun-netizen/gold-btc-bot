import os
import logging
import requests
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# GOLD & BTC SIGNAL BOT V5.9
# CLEAN REBUILD
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
# SETTINGS
# ============================================================

MIN_15M_CANDLES = 60
MIN_H1_CANDLES = 50

EMA_FAST = 20
EMA_SLOW = 50

RSI_PERIOD = 14
ATR_PERIOD = 14
ADX_PERIOD = 14

ZONE_ATR = 0.25
SL_ATR = 1.20
TP1_ATR = 1.20
TP2_ATR = 2.00

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
        "events": "div,splits",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=20,
        )

        if response.status_code != 200:
            logger.warning(
                "%s HTTP %s",
                symbol,
                response.status_code,
            )
            return []

        data = response.json()

        result = (
            data
            .get("chart", {})
            .get("result")
        )

        if not result:
            return []

        result = result[0]

        timestamps = result.get(
            "timestamp",
            [],
        )

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

        for i, timestamp in enumerate(timestamps):

            try:
                o = opens[i]
                h = highs[i]
                l = lows[i]
                c = closes[i]

                if None in (o, h, l, c):
                    continue

                candles.append({
                    "time": timestamp,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                })

            except (
                IndexError,
                TypeError,
                ValueError,
            ):
                continue

        return candles

    except Exception as e:

        logger.error(
            "Yahoo error %s: %s",
            symbol,
            e,
        )

        return []


# ============================================================
# GET CANDLES WITH FALLBACK
# ============================================================

def get_candles(
    asset,
    interval,
    range_value,
):

    for symbol in SYMBOLS.get(asset, []):

        candles = yahoo_candles(
            symbol,
            interval,
            range_value,
        )

        if candles:

            logger.info(
                "%s %s -> %s candles from %s",
                asset,
                interval,
                len(candles),
                symbol,
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
        "1d",
    )

    if candles:
        return candles[-1]["close"], source

    if asset == "gold":

        try:

            response = requests.get(
                "https://api.gold-api.com/price/XAU",
                timeout=15,
            )

            if response.status_code == 200:

                data = response.json()

                price = data.get("price")

                if price is not None:

                    return (
                        float(price),
                        "Gold-API",
                    )

        except Exception as e:

            logger.warning(
                "Gold API error: %s",
                e,
            )

    return None, None


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2.0 / (period + 1)

    value = (
        sum(values[:period])
        / period
    )

    for price in values[period:]:

        value = (
            (price - value)
            * multiplier
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

        change = (
            values[i]
            - values[i - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0.0)

        else:

            gains.append(0.0)
            losses.append(abs(change))

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
        return 100.0

    rs = avg_gain / avg_loss

    return 100.0 - (
        100.0 / (1.0 + rs)
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
            current["high"]
            - current["low"],

            abs(
                current["high"]
                - previous["close"]
            ),

            abs(
                current["low"]
                - previous["close"]
            ),
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

    if len(candles) < (
        period * 2 + 1
    ):
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
            current["high"]
            - current["low"],

            abs(
                current["high"]
                - previous["close"]
            ),

            abs(
                current["low"]
                - previous["close"]
            ),
        )

        trs.append(tr)

        if (
            high_diff > low_diff
            and high_diff > 0
        ):
            plus_dm.append(high_diff)
        else:
            plus_dm.append(0.0)

        if (
            low_diff > high_diff
            and low_diff > 0
        ):
            minus_dm.append(low_diff)
        else:
            minus_dm.append(0.0)

    if len(trs) < period * 2:
        return None

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

        if tr_avg <= 0:
            continue

        plus_di = (
            100.0
            * plus_avg
            / tr_avg
        )

        minus_di = (
            100.0
            * minus_avg
            / tr_avg
        )

        total = (
            plus_di
            + minus_di
        )

        if total <= 0:
            continue

        dx = (
            100.0
            * abs(
                plus_di - minus_di
            )
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

def swing_levels(candles, lookback=40):

    if len(candles) < 10:
        return None, None

    recent = candles[-lookback:]

    swing_low = min(
        c["low"]
        for c in recent
    )

    swing_high = max(
        c["high"]
        for c in recent
    )

    return swing_low, swing_high


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def detect_liquidity_sweep(
    candles,
    swing_low,
    swing_high,
):

    if len(candles) < 3:
        return "NONE"

    c = candles[-1]
    previous = candles[-2]

    tolerance = (
        abs(
            swing_high - swing_low
        ) * 0.003
    )

    bullish_sweep = (
        c["low"] < (
            swing_low + tolerance
        )
        and c["close"] > swing_low
        and c["close"] > c["open"]
    )

    bearish_sweep = (
        c["high"] > (
            swing_high - tolerance
        )
        and c["close"] < swing_high
        and c["close"] < c["open"]
    )

    if bullish_sweep:
        return "BULLISH SWEEP"

    if bearish_sweep:
        return "BEARISH SWEEP"

    # Previous candle sweep
    previous_bullish = (
        previous["low"] < swing_low
        and previous["close"] > swing_low
    )

    previous_bearish = (
        previous["high"] > swing_high
        and previous["close"] < swing_high
    )

    if previous_bullish:
        return "BULLISH SWEEP"

    if previous_bearish:
        return "BEARISH SWEEP"

    return "NONE"


# ============================================================
# CANDLE CONFIRMATION
# ============================================================

def candle_confirmation(candles):

    if len(candles) < 3:
        return "NONE"

    current = candles[-1]
    previous = candles[-2]

    bullish_engulfing = (
        current["close"] > current["open"]
        and previous["close"]
        < previous["open"]
        and current["open"]
        <= previous["close"]
        and current["close"]
        >= previous["open"]
    )

    bearish_engulfing = (
        current["close"] < current["open"]
        and previous["close"]
        > previous["open"]
        and current["open"]
        >= previous["close"]
        and current["close"]
        <= previous["open"]
    )

    if bullish_engulfing:
        return "BULLISH ENGULFING"

    if bearish_engulfing:
        return "BEARISH ENGULFING"

    current_body = abs(
        current["close"]
        - current["open"]
    )

    current_range = (
        current["high"]
        - current["low"]
    )

    if current_range <= 0:
        return "NONE"

    body_ratio = (
        current_body
        / current_range
    )

    if (
        current["close"]
        > current["open"]
        and body_ratio >= 0.65
    ):
        return "BULLISH CANDLE"

    if (
        current["close"]
        < current["open"]
        and body_ratio >= 0.65
    ):
        return "BEARISH CANDLE"

    return "NONE"


# ============================================================
# BREAK OF STRUCTURE
# ============================================================

def detect_bos(
    candles,
    direction,
    lookback=10,
):

    if len(candles) < lookback + 2:
        return "NONE"

    previous = candles[-lookback - 1:-1]
    current = candles[-1]

    previous_high = max(
        c["high"]
        for c in previous
    )

    previous_low = min(
        c["low"]
        for c in previous
    )

    if (
        direction == "BUY"
        and current["close"]
        > previous_high
    ):
        return "BULLISH BOS"

    if (
        direction == "SELL"
        and current["close"]
        < previous_low
    ):
        return "BEARISH BOS"

    return "NONE"


# ============================================================
# RETEST
# ============================================================

def detect_retest(
    candles,
    watch_low,
    watch_high,
    direction,
):

    if len(candles) < 3:
        return "NONE"

    current = candles[-1]

    touched = (
        current["low"]
        <= watch_high
        and current["high"]
        >= watch_low
    )

    if not touched:
        return "NONE"

    if (
        direction == "BUY"
        and current["close"]
        > current["open"]
    ):
        return "BULLISH RETEST"

    if (
        direction == "SELL"
        and current["close"]
        < current["open"]
    ):
        return "BEARISH RETEST"

    return "NONE"


# ============================================================
# ANALYZE
# ============================================================

def analyze_asset(asset):

    candles_15m, source_15m = get_candles(
        asset,
        "15m",
        "5d",
    )

    candles_1h, source_1h = get_candles(
        asset,
        "1h",
        "1mo",
    )

    if len(candles_15m) < MIN_15M_CANDLES:

        logger.warning(
            "%s has only %s 15M candles",
            asset,
            len(candles_15m),
        )

        return None

    closes = [
        c["close"]
        for c in candles_15m
    ]

    price = closes[-1]

    ema20 = ema(
        closes,
        EMA_FAST,
    )

    ema50 = ema(
        closes,
        EMA_SLOW,
    )

    rsi_value = rsi(
        closes,
        RSI_PERIOD,
    )

    atr_value = atr(
        candles_15m,
        ATR_PERIOD,
    )

    adx_value = adx(
        candles_15m,
        ADX_PERIOD,
    )

    structure = market_structure(
        candles_15m
    )

    swing_low, swing_high = swing_levels(
        candles_15m,
        40,
    )

    # ========================================================
    # H1 TREND
    # ========================================================

    h1_trend = "NEUTRAL"

    if len(candles_1h) >= MIN_H1_CANDLES:

        h1_closes = [
            c["close"]
            for c in candles_1h
        ]

        h1_ema20 = ema(
            h1_closes,
            EMA_FAST,
        )

        h1_ema50 = ema(
            h1_closes,
            EMA_SLOW,
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
    # BIAS
    # ========================================================

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

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

    if rsi_value is not None:

        if 50 <= rsi_value <= 70:

            buy_score += 15

            buy_reasons.append(
                "RSI menyokong momentum bullish"
            )

        elif 30 <= rsi_value < 50:

            sell_score += 15

            sell_reasons.append(
                "RSI menyokong momentum bearish"
            )

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

    if buy_score > sell_score:
        bias = "BUY"

    elif sell_score > buy_score:
        bias = "SELL"

    else:
        bias = "NEUTRAL"

    base_confidence = max(
        buy_score,
        sell_score,
    )

    # ========================================================
    # ATR
    # ========================================================

    if (
        atr_value is None
        or atr_value <= 0
    ):

        atr_value = price * 0.005

    # ========================================================
    # WATCH ZONE
    # ========================================================

    zone_size = (
        atr_value * ZONE_ATR
    )

    if bias == "BUY":

        watch_low = (
            price - zone_size
        )

        watch_high = price

    elif bias == "SELL":

        watch_low = price

        watch_high = (
            price + zone_size
        )

    else:

        watch_low = (
            price - zone_size
        )

        watch_high = (
            price + zone_size
        )

    # ========================================================
    # SMART ENTRY ANALYSIS
    # ========================================================

    liquidity = "NONE"

    if (
        swing_low is not None
        and swing_high is not None
    ):

        liquidity = detect_liquidity_sweep(
            candles_15m,
            swing_low,
            swing_high,
        )

    candle = candle_confirmation(
        candles_15m
    )

    bos = detect_bos(
        candles_15m,
        bias,
        10,
    )

    retest = detect_retest(
        candles_15m,
        watch_low,
        watch_high,
        bias,
    )

    # ========================================================
    # ENTRY SCORE
    # ========================================================

    entry_score = 0
    trigger_reasons = []

    if bias == "BUY":

        if liquidity == "BULLISH SWEEP":

            entry_score += 20
            trigger_reasons.append(
                "Bullish liquidity sweep"
            )

        if candle in (
            "BULLISH ENGULFING",
            "BULLISH CANDLE",
        ):

            entry_score += 15
            trigger_reasons.append(
                candle
            )

        if bos == "BULLISH BOS":

            entry_score += 20
            trigger_reasons.append(
                "Bullish BOS"
            )

        if retest == "BULLISH RETEST":

            entry_score += 15
            trigger_reasons.append(
                "Bullish retest"
            )

    elif bias == "SELL":

        if liquidity == "BEARISH SWEEP":

            entry_score += 20
            trigger_reasons.append(
                "Bearish liquidity sweep"
            )

        if candle in (
            "BEARISH ENGULFING",
            "BEARISH CANDLE",
        ):

            entry_score += 15
            trigger_reasons.append(
                candle
            )

        if bos == "BEARISH BOS":

            entry_score += 20
            trigger_reasons.append(
                "Bearish BOS"
            )

        if retest == "BEARISH RETEST":

            entry_score += 15
            trigger_reasons.append(
                "Bearish retest"
            )

    # ========================================================
    # ENTRY TRIGGER
    # ========================================================

    trigger_complete = (
        entry_score >= 55
    )

    if trigger_complete:

        direction = bias

    else:

        direction = "WAIT"

    confidence = min(
        100,
        max(
            55,
            base_confidence
            + entry_score,
        ),
    )

    # Avoid giving excessive confidence
    # when ADX is weak.
    if (
        adx_value is not None
        and adx_value < 20
        and confidence > 75
    ):
        confidence = 75

    # ========================================================
    # SL / TP
    # ========================================================

    if direction == "BUY":

        entry_price = price

        sl = (
            entry_price
            - atr_value * SL_ATR
        )

        tp1 = (
            entry_price
            + atr_value * TP1_ATR
        )

        tp2 = (
            entry_price
            + atr_value * TP2_ATR
        )

    elif direction == "SELL":

        entry_price = price

        sl = (
            entry_price
            + atr_value * SL_ATR
        )

        tp1 = (
            entry_price
            - atr_value * TP1_ATR
        )

        tp2 = (
            entry_price
            - atr_value * TP2_ATR
        )

    else:

        sl = None
        tp1 = None
        tp2 = None

    # ========================================================
    # ANALYSIS
    # ========================================================

    analysis = []

    if bias == "BUY":

        analysis.append(
            "Bias BUY"
        )

    elif bias == "SELL":

        analysis.append(
            "Bias SELL"
        )

    else:

        analysis.append(
            "Bias neutral"
        )

    analysis.extend(
        trigger_reasons
    )

    if not trigger_complete:

        if bias == "BUY":

            if liquidity != "BULLISH SWEEP":

                analysis.append(
                    "Tunggu bullish liquidity sweep"
                )

            if candle not in (
                "BULLISH ENGULFING",
                "BULLISH CANDLE",
            ):

                analysis.append(
                    "Tunggu bullish candle confirmation"
                )

            if bos != "BULLISH BOS":

                analysis.append(
                    "Tunggu bullish BOS"
                )

            if retest != "BULLISH RETEST":

                analysis.append(
                    "Tunggu retest"
                )

        elif bias == "SELL":

            if liquidity != "BEARISH SWEEP":

                analysis.append(
                    "Tunggu bearish liquidity sweep"
                )

            if candle not in (
                "BEARISH ENGULFING",
                "BEARISH CANDLE",
            ):

                analysis.append(
                    "Tunggu bearish candle confirmation"
                )

            if bos != "BEARISH BOS":

                analysis.append(
                    "Tunggu bearish BOS"
                )

            if retest != "BEARISH RETEST":

                analysis.append(
                    "Tunggu retest"
                )

    return {
        "price": price,
        "direction": direction,
        "bias": bias,
        "confidence": confidence,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "entry_score": entry_score,
        "structure": structure,
        "h1_trend": h1_trend,
        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,
        "liquidity": liquidity,
        "candle": candle,
        "bos": bos,
        "retest": retest,
        "watch_low": watch_low,
        "watch_high": watch_high,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "analysis": analysis,
        "source_15m": source_15m,
        "source_1h": source_1h,
    }


# ============================================================
# FORMAT PRICE
# ============================================================

def fmt(value):

    if value is None:
        return "N/A"

    return f"{value:,.2f}"


# ============================================================
# FORMAT SIGNAL
# ============================================================

def format_signal(asset, result):

    if result is None:

        return (
            "❌ *DATA CANDLE GAGAL*\n\n"
            "15M candle tidak mencukupi.\n"
            "Gold akan cuba fallback GC=F / XAUUSD=X.\n\n"
            "🔄 Cuba semula beberapa saat lagi."
        )

    if asset == "gold":

        name = "GOLD (XAUUSD)"
        emoji = "🥇"

    else:

        name = "BTC"
        emoji = "₿"

    direction = result["direction"]

    if direction == "BUY":

        signal_text = (
            "🟢 *SIGNAL: BUY*\n"
            "📈 Entry trigger lengkap"
        )

    elif direction == "SELL":

        signal_text = (
            "🔴 *SIGNAL: SELL*\n"
            "📉 Entry trigger lengkap"
        )

    else:

        signal_text = (
            "🟡 *SIGNAL: WAIT*\n"
            "⏳ Tunggu confirmation"
        )

    rsi_text = (
        f"{result['rsi']:.1f}"
        if result["rsi"] is not None
        else "N/A"
    )

    adx_text = (
        f"{result['adx']:.1f}"
        if result["adx"] is not None
        else "N/A"
    )

    message = (
        f"{emoji} *{name} SIGNAL V5.9*\n\n"
        f"💰 Harga: `${fmt(result['price'])}`\n\n"
        f"{signal_text}\n\n"
        f"🧭 *Bias:* `{result['bias']}`\n"
        f"💯 *Confidence:* `{result['confidence']}%`\n"
        f"📐 *Structure:* `{result['structure']}`\n"
        f"🕐 *1H Trend:* `{result['h1_trend']}`\n"
        f"📊 *RSI:* `{rsi_text}`\n"
        f"📈 *ADX:* `{adx_text}`\n\n"
        f"💧 *LIQUIDITY*\n"
        f"`{result['liquidity']}`\n\n"
        f"🕯 *CANDLE CONFIRMATION*\n"
        f"`{result['candle']}`\n\n"
        f"📐 *BREAK OF STRUCTURE*\n"
        f"`{result['bos']}`\n\n"
        f"🔄 *RETEST*\n"
        f"`{result['retest']}`\n\n"
    )

    if direction == "BUY":

        trigger = "🟢 BUY ENTRY TRIGGER"

    elif direction == "SELL":

        trigger = "🔴 SELL ENTRY TRIGGER"

    else:

        if result["bias"] == "BUY":

            trigger = (
                "🟡 WAIT FOR BUY TRIGGER"
            )

        elif result["bias"] == "SELL":

            trigger = (
                "🟡 WAIT FOR SELL TRIGGER"
            )

        else:

            trigger = "🟡 WAIT"

    message += (
        "⏳ *ENTRY TRIGGER*\n"
        f"{trigger}\n\n"
        "🟡 *WATCH ZONE*\n"
        f"`{fmt(result['watch_low'])} "
        f"– "
        f"{fmt(result['watch_high'])}`\n\n"
        "📉 *SWING LOW*\n"
        f"`{fmt(result['swing_low'])}`\n\n"
        "📈 *SWING HIGH*\n"
        f"`{fmt(result['swing_high'])}`\n\n"
    )

    if direction != "WAIT":

        message += (
            "🛑 *STOP LOSS*\n"
            f"`{fmt(result['sl'])}`\n\n"
            "🎯 *TP1*\n"
            f"`{fmt(result['tp1'])}`\n\n"
            "🎯 *TP2*\n"
            f"`{fmt(result['tp2'])}`\n\n"
        )

    message += "🧠 *ANALYSIS*\n"

    for item in result["analysis"]:

        message += (
            f"• {item}\n"
        )

    message += (
        "\n📡 *DATA SOURCE*\n"
        f"15M: `{result['source_15m']}`\n"
        f"1H: `{result['source_1h']}`\n\n"
        "⚠️ Technical signal sahaja. "
        "Bukan jaminan profit.\n"
        "🚫 Tiada auto-trading."
    )

    return message


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "🤖 *GOLD & BTC SIGNAL BOT V5.9*\n\n"
        "📌 *COMMANDS*\n\n"
        "/price\n"
        "➡️ Harga Gold & BTC\n\n"
        "/signal gold\n"
        "➡️ Signal Gold\n\n"
        "/signal btc\n"
        "➡️ Signal BTC\n\n"
        "/news\n"
        "➡️ News monitor\n\n"
        "🧠 Technical Engine V5.9\n"
        "📊 15M + 1H\n"
        "📐 Market Structure\n"
        "📈 EMA / RSI / ADX / ATR\n"
        "💧 Liquidity Sweep\n"
        "🕯 Candle Confirmation\n"
        "📐 BOS\n"
        "🔄 Retest\n"
        "🎯 Entry Zone / SL / TP\n"
        "🚫 Tiada auto-trading"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# ============================================================
# PRICE
# ============================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    gold, gold_source = get_live_price(
        "gold"
    )

    btc, btc_source = get_live_price(
        "btc"
    )

    text = (
        "📈 *HARGA SEMASA V5.9*\n\n"
    )

    if gold is not None:

        text += (
            "🥇 *Gold XAUUSD*\n"
            f"`${fmt(gold)}`\n"
            f"Source: `{gold_source}`\n\n"
        )

    else:

        text += (
            "🥇 Gold: ❌ Gagal\n\n"
        )

    if btc is not None:

        text += (
            "₿ *Bitcoin BTC*\n"
            f"`${fmt(btc)}`\n"
            f"Source: `{btc_source}`\n"
        )

    else:

        text += (
            "₿ BTC: ❌ Gagal\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# ============================================================
# SIGNAL
# ============================================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
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
        .strip()
    )

    if asset not in (
        "gold",
        "btc",
    ):

        await update.message.reply_text(
            "❌ Asset tidak disokong.\n\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    status = await update.message.reply_text(
        "🧠 *SIGNAL V5.9*\n\n"
        "📡 Mengambil data market...\n"
        "📊 15M + 1H\n"
        "💧 Checking liquidity...\n"
        "🕯 Checking candle...\n"
        "📐 Checking BOS...\n"
        "🔄 Checking retest...\n"
        "⏳ Sila tunggu..."
    )

    try:

        result = analyze_asset(
            asset
        )

        message = format_signal(
            asset,
            result,
        )

        await status.edit_text(
            message,
            parse_mode="Markdown",
        )

    except Exception as e:

        logger.exception(
            "Signal error"
        )

        await status.edit_text(
            "❌ *SIGNAL ERROR*\n\n"
            f"`{str(e)}`",
            parse_mode="Markdown",
        )


# ============================================================
# NEWS
# ============================================================

async def news(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "📰 *NEWS MONITOR V5.9*\n\n"
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
        "⚠️ News engine belum mengambil "
        "berita live."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.error(
        "Telegram error",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("==========================================")
    print("🤖 GOLD & BTC SIGNAL BOT V5.9")
    print("==========================================")

    if not TOKEN:

        print("")
        print("❌ BOT_TOKEN TIDAK DIJUMPAI")
        print("")
        print(
            "Set environment variable:"
        )
        print(
            "BOT_TOKEN=<token BotFather>"
        )
        print("")

        return

    print(
        "✅ BOT_TOKEN berjaya dibaca!"
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
                start,
            )
        )

        application.add_handler(
            CommandHandler(
                "price",
                price,
            )
        )

        application.add_handler(
            CommandHandler(
                "signal",
                signal,
            )
        )

        application.add_handler(
            CommandHandler(
                "news",
                news,
            )
        )

        application.add_error_handler(
            error_handler
        )

        print(
            "🚀 V5.9 BOT AKTIF!"
        )

        print(
            "📡 Telegram polling aktif!"
        )

        print(
            "🥇 Gold: GC=F / XAUUSD=X"
        )

        print(
            "₿ BTC: BTC-USD"
        )

        print(
            "📊 15M + 1H"
        )

        print(
            "💧 Liquidity + Candle + BOS + Retest"
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
    main()logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# ============================================================
# SYMBOLS
# ============================================================

SYMBOLS = {
    "gold": ["GC=F", "XAUUSD=X"],
    "btc": ["BTC-USD"],
}

# ============================================================
# SETTINGS
# ============================================================

MIN_15M_CANDLES = 60

SWING_LOOKBACK = 20

ZONE_ATR = 0.25

SL_ATR_BUFFER = 0.20

MIN_RR = 1.5

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
                "Mozilla/5.0 "
                "(Android 10; Mobile)"
            },
            timeout=20
        )

        if response.status_code != 200:

            logger.warning(
                f"{symbol} HTTP {response.status_code}"
            )

            return []

        data = response.json()

        chart = data.get("chart", {})

        result = chart.get("result")

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

                if (
                    o is None
                    or h is None
                    or l is None
                    or c is None
                ):
                    continue

                candles.append({
                    "time": timestamps[i],
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
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
            f"Yahoo error {symbol}: {e}"
        )

        return []


# ============================================================
# GET CANDLES WITH FALLBACK
# ============================================================

def get_candles(asset, interval, range_value):

    symbols = SYMBOLS.get(asset, [])

    for symbol in symbols:

        candles = yahoo_candles(
            symbol,
            interval,
            range_value
        )

        if candles:

            logger.info(
                f"{asset} {interval}: "
                f"{len(candles)} candles "
                f"from {symbol}"
            )

            return candles, symbol

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

    # --------------------------------------------------------
    # GOLD API FALLBACK
    # --------------------------------------------------------

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

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    value = (
        sum(values[:period])
        / period
    )

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

def adx(candles, period=14):

    if len(candles) < (
        period * 2 + 1
    ):
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

def get_swings(candles):

    recent = candles[-SWING_LOOKBACK:]

    swing_high = max(
        c["high"]
        for c in recent
    )

    swing_low = min(
        c["low"]
        for c in recent
    )

    return swing_low, swing_high


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def detect_liquidity(candles):

    if len(candles) < 25:

        return {
            "type": "NONE",
            "level": None
        }

    previous = candles[-21:-1]

    current = candles[-1]

    previous_low = min(
        c["low"]
        for c in previous
    )

    previous_high = max(
        c["high"]
        for c in previous
    )

    # --------------------------------------------------------
    # BULLISH SWEEP
    # Price breaks previous low and closes back above it
    # --------------------------------------------------------

    if (
        current["low"] < previous_low
        and current["close"] > previous_low
    ):

        return {
            "type": "BULLISH SWEEP",
            "level": previous_low
        }

    # --------------------------------------------------------
    # BEARISH SWEEP
    # --------------------------------------------------------

    if (
        current["high"] > previous_high
        and current["close"] < previous_high
    ):

        return {
            "type": "BEARISH SWEEP",
            "level": previous_high
        }

    return {
        "type": "NONE",
        "level": None
    }


# ============================================================
# CANDLE CONFIRMATION
# ============================================================

def candle_confirmation(candles):

    if len(candles) < 3:

        return "NONE"

    previous = candles[-2]
    current = candles[-1]

    # --------------------------------------------------------
    # Bullish engulfing
    # --------------------------------------------------------

    bullish = (
        previous["close"]
        < previous["open"]
        and current["close"]
        > current["open"]
        and current["open"]
        <= previous["close"]
        and current["close"]
        >= previous["open"]
    )

    if bullish:
        return "BULLISH ENGULFING"

    # --------------------------------------------------------
    # Bearish engulfing
    # --------------------------------------------------------

    bearish = (
        previous["close"]
        > previous["open"]
        and current["close"]
        < current["open"]
        and current["open"]
        >= previous["close"]
        and current["close"]
        <= previous["open"]
    )

    if bearish:
        return "BEARISH ENGULFING"

    # --------------------------------------------------------
    # Strong bullish candle
    # --------------------------------------------------------

    body = abs(
        current["close"]
        - current["open"]
    )

    candle_range = (
        current["high"]
        - current["low"]
    )

    if candle_range > 0:

        body_ratio = (
            body / candle_range
        )

        if (
            current["close"]
            > current["open"]
            and body_ratio >= 0.65
        ):

            return "BULLISH CANDLE"

        if (
            current["close"]
            < current["open"]
            and body_ratio >= 0.65
        ):

            return "BEARISH CANDLE"

    return "NONE"


# ============================================================
# BREAK OF STRUCTURE
# ============================================================

def detect_bos(candles):

    if len(candles) < 12:

        return "NONE"

    current = candles[-1]

    previous = candles[-11:-1]

    previous_high = max(
        c["high"]
        for c in previous
    )

    previous_low = min(
        c["low"]
        for c in previous
    )

    if current["close"] > previous_high:

        return "BULLISH BOS"

    if current["close"] < previous_low:

        return "BEARISH BOS"

    return "NONE"


# ============================================================
# RETEST
# ============================================================

def detect_retest(
    candles,
    direction,
    zone_low,
    zone_high
):

    if len(candles) < 2:

        return False

    current = candles[-1]

    # --------------------------------------------------------
    # BUY RETEST
    # --------------------------------------------------------

    if direction == "BUY":

        touched = (
            current["low"]
            <= zone_high
            and current["high"]
            >= zone_low
        )

        holding = (
            current["close"]
            >= zone_low
        )

        return (
            touched
            and holding
        )

    # --------------------------------------------------------
    # SELL RETEST
    # --------------------------------------------------------

    if direction == "SELL":

        touched = (
            current["high"]
            >= zone_low
            and current["low"]
            <= zone_high
        )

        holding = (
            current["close"]
            <= zone_high
        )

        return (
            touched
            and holding
        )

    return False


# ============================================================
# ROUND PRICE
# ============================================================

def round_price(price):

    if price is None:
        return None

    if price >= 10000:
        return round(price, 2)

    if price >= 1000:
        return round(price, 2)

    if price >= 100:
        return round(price, 2)

    return round(price, 4)


# ============================================================
# ANALYZE ASSET
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

    if len(candles_15m) < MIN_15M_CANDLES:

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

    structure = market_structure(
        candles_15m
    )

    swing_low, swing_high = get_swings(
        candles_15m
    )

    liquidity = detect_liquidity(
        candles_15m
    )

    candle = candle_confirmation(
        candles_15m
    )

    bos = detect_bos(
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
    # BIAS SCORE
    # ========================================================

    buy_score = 0
    sell_score = 0

    reasons = []

    # EMA
    if (
        ema20 is not None
        and ema50 is not None
    ):

        if ema20 > ema50:

            buy_score += 20

            reasons.append(
                "EMA20 di atas EMA50"
            )

        elif ema20 < ema50:

            sell_score += 20

            reasons.append(
                "EMA20 di bawah EMA50"
            )

    # RSI
    if rsi_value is not None:

        if 50 <= rsi_value <= 70:

            buy_score += 15

            reasons.append(
                "RSI menyokong momentum bullish"
            )

        elif 30 <= rsi_value < 50:

            sell_score += 15

            reasons.append(
                "RSI menyokong momentum bearish"
            )

    # Structure
    if structure == "BULLISH":

        buy_score += 20

        reasons.append(
            "Market structure bullish"
        )

    elif structure == "BEARISH":

        sell_score += 20

        reasons.append(
            "Market structure bearish"
        )

    # H1
    if h1_trend == "BULLISH":

        buy_score += 20

        reasons.append(
            "Trend 1H bullish"
        )

    elif h1_trend == "BEARISH":

        sell_score += 20

        reasons.append(
            "Trend 1H bearish"
        )

    # ========================================================
    # DETERMINE BIAS
    # ========================================================

    if (
        buy_score >= 40
        and buy_score > sell_score
    ):

        bias = "BUY"

        confidence = buy_score

    elif (
        sell_score >= 40
        and sell_score > buy_score
    ):

        bias = "SELL"

        confidence = sell_score

    else:

        bias = "NEUTRAL"

        confidence = max(
            buy_score,
            sell_score
        )

    # ========================================================
    # ATR FALLBACK
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
        atr_value * ZONE_ATR
    )

    # For a BUY bias, zone is near liquidity/swing low.
    # For SELL bias, zone is near liquidity/swing high.

    if bias == "BUY":

        base = swing_low

        if (
            liquidity["type"]
            == "BULLISH SWEEP"
            and liquidity["level"]
            is not None
        ):

            base = liquidity["level"]

        zone_low = (
            base
            - zone_size * 0.20
        )

        zone_high = (
            base
            + zone_size
        )

    elif bias == "SELL":

        base = swing_high

        if (
            liquidity["type"]
            == "BEARISH SWEEP"
            and liquidity["level"]
            is not None
        ):

            base = liquidity["level"]

        zone_low = (
            base
            - zone_size
        )

        zone_high = (
            base
            + zone_size * 0.20
        )

    else:

        zone_low = (
            price - zone_size
        )

        zone_high = (
            price + zone_size
        )

    # ========================================================
    # RETEST
    # ========================================================

    retest = detect_retest(
        candles_15m,
        bias,
        zone_low,
        zone_high
    )

    # ========================================================
    # CONFIRMATION CHECKS
    # ========================================================

    bullish_sweep = (
        liquidity["type"]
        == "BULLISH SWEEP"
    )

    bearish_sweep = (
        liquidity["type"]
        == "BEARISH SWEEP"
    )

    bullish_candle = (
        candle in (
            "BULLISH ENGULFING",
            "BULLISH CANDLE"
        )
    )

    bearish_candle = (
        candle in (
            "BEARISH ENGULFING",
            "BEARISH CANDLE"
        )
    )

    bullish_bos = (
        bos == "BULLISH BOS"
    )

    bearish_bos = (
        bos == "BEARISH BOS"
    )

    # ========================================================
    # SETUP SCORE
    # ========================================================

    setup_score = 0

    if bias == "BUY":

        if bullish_sweep:
            setup_score += 20

        if bullish_candle:
            setup_score += 20

        if bullish_bos:
            setup_score += 25

        if retest:
            setup_score += 25

        if h1_trend == "BULLISH":
            setup_score += 10

    elif bias == "SELL":

        if bearish_sweep:
            setup_score += 20

        if bearish_candle:
            setup_score += 20

        if bearish_bos:
            setup_score += 25

        if retest:
            setup_score += 25

        if h1_trend == "BEARISH":
            setup_score += 10

    # ========================================================
    # SETUP QUALITY
    # ========================================================

    if setup_score >= 80:

        quality = "A+"

    elif setup_score >= 65:

        quality = "A"

    elif setup_score >= 50:

        quality = "B"

    elif setup_score >= 30:

        quality = "C"

    else:

        quality = "D"

    # ========================================================
    # STATUS
    # ========================================================

    if bias == "BUY":

        if (
            bullish_sweep
            and bullish_candle
            and bullish_bos
            and retest
        ):

            status = "ENTRY CONFIRMED"

        elif (
            bullish_sweep
            or bullish_candle
            or bullish_bos
        ):

            status = "ARMED"

        else:

            status = "WAIT"

    elif bias == "SELL":

        if (
            bearish_sweep
            and bearish_candle
            and bearish_bos
            and retest
        ):

            status = "ENTRY CONFIRMED"

        elif (
            bearish_sweep
            or bearish_candle
            or bearish_bos
        ):

            status = "ARMED"

        else:

            status = "WAIT"

    else:

        status = "WAIT"

    # ========================================================
    # ENTRY
    # ========================================================

    if status == "ENTRY CONFIRMED":

        entry = price

    elif status == "ARMED":

        entry = (
            zone_low
            + (
                zone_high
                - zone_low
            ) / 2
        )

    else:

        entry = None

    # ========================================================
    # SL / TP
    # ========================================================

    sl = None
    tp1 = None
    tp2 = None
    rr1 = None
    rr2 = None

    if bias == "BUY":

        if entry is not None:

            sl = min(
                swing_low,
                zone_low
            ) - (
                atr_value
                * SL_ATR_BUFFER
            )

            risk = (
                entry - sl
            )

            if risk > 0:

                tp1 = entry + (
                    risk * 1.5
                )

                tp2 = entry + (
                    risk * 2.0
                )

                rr1 = 1.5
                rr2 = 2.0

    elif bias == "SELL":

        if entry is not None:

            sl = max(
                swing_high,
                zone_high
            ) + (
                atr_value
                * SL_ATR_BUFFER
            )

            risk = (
                sl - entry
            )

            if risk > 0:

                tp1 = entry - (
                    risk * 1.5
                )

                tp2 = entry - (
                    risk * 2.0
                )

                rr1 = 1.5
                rr2 = 2.0

    # ========================================================
    # FINAL REASONS
    # ========================================================

    if bias == "BUY":

        if not bullish_sweep:

            reasons.append(
                "Tunggu bullish liquidity sweep"
            )

        if not bullish_candle:

            reasons.append(
                "Tunggu bullish candle confirmation"
            )

        if not bullish_bos:

            reasons.append(
                "Tunggu bullish BOS"
            )

        if not retest:

            reasons.append(
                "Tunggu retest watch zone"
            )

    elif bias == "SELL":

        if not bearish_sweep:

            reasons.append(
                "Tunggu bearish liquidity sweep"
            )

        if not bearish_candle:

            reasons.append(
                "Tunggu bearish candle confirmation"
            )

        if not bearish_bos:

            reasons.append(
                "Tunggu bearish BOS"
            )

        if not retest:

            reasons.append(
                "Tunggu retest watch zone"
            )

    else:

        reasons.append(
            "Bias belum cukup kuat"
        )

    return {
        "price": price,
        "bias": bias,
        "status": status,
        "confidence": confidence,
        "setup_score": setup_score,
        "quality": quality,
        "structure": structure,
        "h1_trend": h1_trend,
        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,
        "liquidity": liquidity["type"],
        "liquidity_level": liquidity["level"],
        "candle": candle,
        "bos": bos,
        "retest": retest,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "rr1": rr1,
        "rr2": rr2,
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
            "Gold akan cuba fallback GC=F / Gold API.\n\n"
            "🔄 Cuba semula selepas beberapa saat."
        )

    if asset == "gold":

        name = "GOLD (XAUUSD)"
        emoji = "🥇"

    else:

        name = "BTC"
        emoji = "₿"

    price = result["price"]

    bias = result["bias"]

    status = result["status"]

    confidence = result["confidence"]

    setup_score = result["setup_score"]

    quality = result["quality"]

    rsi_value = result["rsi"]

    adx_value = result["adx"]

    # ========================================================
    # HEADER
    # ========================================================

    message = (
        f"{emoji} *{name} SIGNAL V5.8*\n\n"
        f"💰 Harga: `${price:,.2f}`\n"
    )

    # ========================================================
    # SIGNAL
    # ========================================================

    if status == "ENTRY CONFIRMED":

        if bias == "BUY":

            message += (
                "\n🟢 *SIGNAL: BUY*\n"
                "🚀 ENTRY CONFIRMED\n"
            )

        else:

            message += (
                "\n🔴 *SIGNAL: SELL*\n"
                "🚀 ENTRY CONFIRMED\n"
            )

    elif status == "ARMED":

        if bias == "BUY":

            message += (
                "\n🟢 *BIAS: BUY*\n"
                "🟠 SETUP ARMED\n"
            )

        elif bias == "SELL":

            message += (
                "\n🔴 *BIAS: SELL*\n"
                "🟠 SETUP ARMED\n"
            )

        else:

            message += (
                "\n🟡 *SIGNAL: WAIT*\n"
            )

    else:

        message += (
            "\n🟡 *SIGNAL: WAIT*\n"
            "⏳ Tunggu confirmation\n"
        )

    # ========================================================
    # QUALITY
    # ========================================================

    message += (
        f"\n🧭 Bias: `{bias}`\n"
        f"💯 Confidence: `{confidence}%`\n"
        f"⭐ Setup Quality: `{quality}`\n"
        f"📊 Setup Score: `{setup_score}/100`\n"
        f"📐 Structure: `{result['structure']}`\n"
        f"🕐 1H Trend: `{result['h1_trend']}`\n"
        f"📊 RSI: `{rsi_value:.1f}`\n"
        f"📈 ADX: `{adx_value:.1f}`\n\n"
    )

    # ========================================================
    # LIQUIDITY
    # ========================================================

    message += (
        "💧 *LIQUIDITY*\n"
        f"`{result['liquidity']}`\n\n"
    )

    # ========================================================
    # CANDLE
    # ========================================================

    message += (
        "🕯 *CANDLE CONFIRMATION*\n"
        f"`{result['candle']}`\n\n"
    )

    # ========================================================
    # BOS
    # ========================================================

    message += (
        "📐 *BREAK OF STRUCTURE*\n"
        f"`{result['bos']}`\n\n"
    )

    # ========================================================
    # RETEST
    # ========================================================

    if result["retest"]:

        retest_text = "CONFIRMED"

    else:

        retest_text = "NONE"

    message += (
        "🔄 *RETEST*\n"
        f"`{retest_text}`\n\n"
    )

    # ========================================================
    # ENTRY STATUS
    # ========================================================

    if status == "ENTRY CONFIRMED":

        message += (
            "🚀 *ENTRY TRIGGER*\n"
            "🟢 ENTRY CONFIRMED\n\n"
        )

    elif status == "ARMED":

        message += (
            "⏳ *ENTRY TRIGGER*\n"
            "🟠 SETUP ARMED — TUNGGU CONFIRMATION AKHIR\n\n"
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
        f"`{result['zone_low']:,.2f} "
        f"– "
        f"{result['zone_high']:,.2f}`\n\n"
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
    # ENTRY / SL / TP
    # ========================================================

    if result["entry"] is not None:

        message += (
            "🎯 *ENTRY*\n"
            f"`{result['entry']:,.2f}`\n\n"
        )

        if result["sl"] is not None:

            message += (
                "🛑 *STOP LOSS*\n"
                f"`{result['sl']:,.2f}`\n\n"
            )

        if result["tp1"] is not None:

            message += (
                "🎯 *TP1*\n"
                f"`{result['tp1']:,.2f}`\n"
                f"R:R `1:{result['rr1']:.1f}`\n\n"
            )

        if result["tp2"] is not None:

            message += (
                "🎯 *TP2*\n"
                f"`{result['tp2']:,.2f}`\n"
                f"R:R `1:{result['rr2']:.1f}`\n\n"
            )

    else:

        message += (
            "🎯 *ENTRY*\n"
            "`WAIT`\n\n"
            "🛑 *STOP LOSS*\n"
            "`WAIT`\n\n"
            "🎯 *TP1 / TP2*\n"
            "`WAIT`\n\n"
        )

    # ========================================================
    # ANALYSIS
    # ========================================================

    message += "🧠 *ANALYSIS*\n"

    shown = 0

    for reason in result["reasons"]:

        message += (
            f"• {reason}\n"
        )

        shown += 1

        if shown >= 8:
            break

    # ========================================================
    # SOURCE
    # ========================================================

    message += (
        "\n📡 *DATA SOURCE*\n"
        f"15M: `{result['source_15m']}`\n"
        f"1H: `{result['source_1h']}`\n\n"
        "🚫 Tiada auto-trading.\n"
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
        "🤖 *GOLD & BTC SIGNAL BOT V5.8*\n\n"

        "📌 *COMMANDS*\n\n"

        "/price\n"
        "➡️ Harga Gold & BTC\n\n"

        "/signal gold\n"
        "➡️ Signal Gold V5.8\n\n"

        "/signal btc\n"
        "➡️ Signal BTC V5.8\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 Technical Engine V5.8\n"
        "📊 15M + 1H\n"
        "📐 Market Structure\n"
        "💧 Liquidity Sweep\n"
        "🕯 Candle Confirmation\n"
        "📐 BOS\n"
        "🔄 Retest\n"
        "⭐ Setup Quality\n"
        "🎯 Entry / SL / TP\n"
        "📊 Risk : Reward\n"
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

    gold, gold_source = get_live_price(
        "gold"
    )

    btc, btc_source = get_live_price(
        "btc"
    )

    text = (
        "📈 *HARGA SEMASA V5.8*\n\n"
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

    status_message = await update.message.reply_text(
        "🧠 *SIGNAL V5.8*\n\n"
        "📡 Mengambil candle...\n"
        "📊 15M + 1H\n"
        "💧 Mencari liquidity...\n"
        "🕯 Mencari candle confirmation...\n"
        "📐 Mengesan BOS...\n"
        "🔄 Mengesan retest...\n"
        "⏳ Sila tunggu..."
    )

    try:

        result = analyze_asset(
            asset
        )

        message = format_signal(
            asset,
            result
        )

        await status_message.edit_text(
            message,
            parse_mode="Markdown"
        )

    except Exception as e:

        logger.exception(
            "Signal error"
        )

        await status_message.edit_text(
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
        "📰 *NEWS MONITOR V5.8*\n\n"

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

        "⚠️ News engine belum live."
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
    print("🤖 GOLD & BTC SIGNAL BOT V5.8")
    print("==========================================")

    if not TOKEN:

        print("")
        print("❌ BOT_TOKEN TIDAK DIJUMPAI")
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
        "🤖 Starting V5.8..."
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
            "🚀 V5.8 BOT AKTIF!"
        )

        print(
            "📡 Telegram polling aktif!"
        )

        print(
            "🥇 Gold: GC=F → XAUUSD=X"
        )

        print(
            "₿ BTC: BTC-USD"
        )

        print(
            "📊 Timeframe: 15M + 1H"
        )

        print(
            "💧 Liquidity Sweep"
        )

        print(
            "🕯 Candle Confirmation"
        )

        print(
            "📐 BOS"
        )

        print(
            "🔄 Retest"
        )

        print(
            "⭐ Setup Quality"
        )

        print(
            "🎯 Entry / SL / TP"
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
