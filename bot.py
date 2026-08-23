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
# GOLD & BTC SIGNAL BOT V5.6
# ENTRY CONFIRMATION ENGINE
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

MIN_CANDLES_15M = 80
MIN_CANDLES_1H = 60

SWING_LOOKBACK = 20
LIQUIDITY_LOOKBACK = 10

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
                f"{symbol} HTTP {response.status_code}"
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
            []
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
# GET CANDLES
# ============================================================

def get_candles(
    asset,
    interval,
    range_value
):

    for symbol in SYMBOLS.get(
        asset,
        []
    ):

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

    candles, source = get_candles(
        asset,
        "1m",
        "1d"
    )

    if candles:

        return (
            candles[-1]["close"],
            source
        )

    # GOLD API FALLBACK

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

        plus_dm.append(
            high_diff
            if (
                high_diff > low_diff
                and high_diff > 0
            )
            else 0
        )

        minus_dm.append(
            low_diff
            if (
                low_diff > high_diff
                and low_diff > 0
            )
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

def get_swing_levels(candles):

    if len(candles) < SWING_LOOKBACK:
        return None, None

    data = candles[
        -SWING_LOOKBACK:
    ]

    swing_high = max(
        c["high"]
        for c in data[:-1]
    )

    swing_low = min(
        c["low"]
        for c in data[:-1]
    )

    return (
        swing_low,
        swing_high
    )


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def detect_liquidity_sweep(candles):

    if len(candles) < (
        LIQUIDITY_LOOKBACK + 3
    ):

        return {
            "type": "NONE",
            "level": None
        }

    previous = candles[
        -LIQUIDITY_LOOKBACK - 2:
        -2
    ]

    last = candles[-2]

    previous_low = min(
        c["low"]
        for c in previous
    )

    previous_high = max(
        c["high"]
        for c in previous
    )

    # Bullish liquidity sweep:
    # wick below liquidity then close back above

    if (
        last["low"] < previous_low
        and last["close"] > previous_low
    ):

        return {
            "type": "BULLISH SWEEP",
            "level": previous_low
        }

    # Bearish liquidity sweep:
    # wick above liquidity then close back below

    if (
        last["high"] > previous_high
        and last["close"] < previous_high
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

    if len(candles) < 4:

        return "NONE"

    candle = candles[-2]

    body = abs(
        candle["close"]
        - candle["open"]
    )

    candle_range = (
        candle["high"]
        - candle["low"]
    )

    if candle_range <= 0:
        return "NONE"

    body_ratio = (
        body
        / candle_range
    )

    upper_wick = (
        candle["high"]
        - max(
            candle["open"],
            candle["close"]
        )
    )

    lower_wick = (
        min(
            candle["open"],
            candle["close"]
        )
        - candle["low"]
    )

    # Bullish engulfing

    previous = candles[-3]

    bullish_engulfing = (
        candle["close"]
        > candle["open"]
        and previous["close"]
        < previous["open"]
        and candle["close"]
        >= previous["open"]
        and candle["open"]
        <= previous["close"]
    )

    # Bearish engulfing

    bearish_engulfing = (
        candle["close"]
        < candle["open"]
        and previous["close"]
        > previous["open"]
        and candle["open"]
        >= previous["close"]
        and candle["close"]
        <= previous["open"]
    )

    if bullish_engulfing:
        return "BULLISH ENGULFING"

    if bearish_engulfing:
        return "BEARISH ENGULFING"

    # Strong bullish candle

    if (
        candle["close"]
        > candle["open"]
        and body_ratio >= 0.60
        and lower_wick <= body * 0.8
    ):
        return "BULLISH CANDLE"

    # Strong bearish candle

    if (
        candle["close"]
        < candle["open"]
        and body_ratio >= 0.60
        and upper_wick <= body * 0.8
    ):
        return "BEARISH CANDLE"

    return "NONE"


# ============================================================
# BREAK OF STRUCTURE
# ============================================================

def detect_bos(candles):

    if len(candles) < 12:

        return "NONE"

    data = candles[-12:-2]

    reference_high = max(
        c["high"]
        for c in data
    )

    reference_low = min(
        c["low"]
        for c in data
    )

    confirmation = candles[-2]

    if (
        confirmation["close"]
        > reference_high
    ):

        return "BULLISH BOS"

    if (
        confirmation["close"]
        < reference_low
    ):

        return "BEARISH BOS"

    return "NONE"


# ============================================================
# RETEST
# ============================================================

def detect_retest(
    price,
    entry_low,
    entry_high
):

    if (
        entry_low
        <= price
        <= entry_high
    ):

        return True

    return False


# ============================================================
# BIAS
# ============================================================

def calculate_bias(
    ema20,
    ema50,
    structure,
    h1_trend
):

    buy = 0
    sell = 0

    if (
        ema20 is not None
        and ema50 is not None
    ):

        if ema20 > ema50:
            buy += 1

        elif ema20 < ema50:
            sell += 1

    if structure == "BULLISH":
        buy += 1

    elif structure == "BEARISH":
        sell += 1

    if h1_trend == "BULLISH":
        buy += 1

    elif h1_trend == "BEARISH":
        sell += 1

    if buy > sell:
        return "BUY"

    if sell > buy:
        return "SELL"

    return "NEUTRAL"


# ============================================================
# ANALYZE V5.6
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

    if len(candles_15m) < MIN_CANDLES_15M:

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

    # ========================================================
    # H1 TREND
    # ========================================================

    h1_trend = "NEUTRAL"

    if len(candles_1h) >= MIN_CANDLES_1H:

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
    # BIAS
    # ========================================================

    bias = calculate_bias(
        ema20,
        ema50,
        structure,
        h1_trend
    )

    # ========================================================
    # SWINGS
    # ========================================================

    swing_low, swing_high = (
        get_swing_levels(
            candles_15m
        )
    )

    if swing_low is None:

        swing_low = price

    if swing_high is None:

        swing_high = price

    # ========================================================
    # LIQUIDITY
    # ========================================================

    liquidity = (
        detect_liquidity_sweep(
            candles_15m
        )
    )

    liquidity_type = liquidity[
        "type"
    ]

    # ========================================================
    # CANDLE
    # ========================================================

    candle_type = (
        candle_confirmation(
            candles_15m
        )
    )

    # ========================================================
    # BOS
    # ========================================================

    bos = detect_bos(
        candles_15m
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

    zone_size = atr_value * 0.25

    if bias == "BUY":

        zone_center = (
            swing_low
            + atr_value * 0.25
        )

    elif bias == "SELL":

        zone_center = (
            swing_high
            - atr_value * 0.25
        )

    else:

        zone_center = price

    entry_low = (
        zone_center
        - zone_size
    )

    entry_high = (
        zone_center
        + zone_size
    )

    # ========================================================
    # RETEST
    # ========================================================

    in_zone = detect_retest(
        price,
        entry_low,
        entry_high
    )

    # ========================================================
    # CONFIRMATION SCORE
    # ========================================================

    score = 0

    reasons = []

    missing = []

    # Bias

    if bias in (
        "BUY",
        "SELL"
    ):

        score += 20

        reasons.append(
            f"Bias {bias}"
        )

    else:

        missing.append(
            "Bias belum jelas"
        )

    # Liquidity

    if bias == "BUY":

        if (
            liquidity_type
            == "BULLISH SWEEP"
        ):

            score += 20

            reasons.append(
                "Bullish liquidity sweep"
            )

        else:

            missing.append(
                "Bullish liquidity sweep"
            )

    elif bias == "SELL":

        if (
            liquidity_type
            == "BEARISH SWEEP"
        ):

            score += 20

            reasons.append(
                "Bearish liquidity sweep"
            )

        else:

            missing.append(
                "Bearish liquidity sweep"
            )

    # Candle

    if bias == "BUY":

        if candle_type in (
            "BULLISH CANDLE",
            "BULLISH ENGULFING"
        ):

            score += 20

            reasons.append(
                candle_type
            )

        else:

            missing.append(
                "Bullish candle confirmation"
            )

    elif bias == "SELL":

        if candle_type in (
            "BEARISH CANDLE",
            "BEARISH ENGULFING"
        ):

            score += 20

            reasons.append(
                candle_type
            )

        else:

            missing.append(
                "Bearish candle confirmation"
            )

    # BOS

    if bias == "BUY":

        if bos == "BULLISH BOS":

            score += 20

            reasons.append(
                "Bullish BOS"
            )

        else:

            missing.append(
                "Bullish BOS"
            )

    elif bias == "SELL":

        if bos == "BEARISH BOS":

            score += 20

            reasons.append(
                "Bearish BOS"
            )

        else:

            missing.append(
                "Bearish BOS"
            )

    # Retest

    if in_zone:

        score += 20

        reasons.append(
            "Harga berada dalam watch zone"
        )

    else:

        missing.append(
            "Retest watch zone"
        )

    # ========================================================
    # FINAL ENTRY TRIGGER
    # ========================================================

    required_confirmations = (
        liquidity_type != "NONE"
        and candle_type != "NONE"
        and bos != "NONE"
        and in_zone
    )

    if (
        bias == "BUY"
        and liquidity_type
        == "BULLISH SWEEP"
        and candle_type in (
            "BULLISH CANDLE",
            "BULLISH ENGULFING"
        )
        and bos == "BULLISH BOS"
        and in_zone
    ):

        direction = "BUY"

        trigger = (
            "BUY ENTRY CONFIRMED"
        )

    elif (
        bias == "SELL"
        and liquidity_type
        == "BEARISH SWEEP"
        and candle_type in (
            "BEARISH CANDLE",
            "BEARISH ENGULFING"
        )
        and bos == "BEARISH BOS"
        and in_zone
    ):

        direction = "SELL"

        trigger = (
            "SELL ENTRY CONFIRMED"
        )

    else:

        direction = "WAIT"

        trigger = (
            "WAIT FOR ENTRY TRIGGER"
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence = min(
        score,
        100
    )

    # Minimum display confidence
    if direction == "WAIT":

        confidence = max(
            confidence,
            55
        )

    # ========================================================
    # SL / TP
    # ========================================================

    if direction == "BUY":

        sl = (
            entry_low
            - atr_value * 0.75
        )

        risk = (
            price - sl
        )

        tp1 = (
            price
            + risk * 1.5
        )

        tp2 = (
            price
            + risk * 2.0
        )

    elif direction == "SELL":

        sl = (
            entry_high
            + atr_value * 0.75
        )

        risk = (
            sl - price
        )

        tp1 = (
            price
            - risk * 1.5
        )

        tp2 = (
            price
            - risk * 2.0
        )

    else:

        sl = None
        tp1 = None
        tp2 = None

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "price": price,
        "direction": direction,
        "bias": bias,
        "confidence": confidence,

        "structure": structure,
        "h1_trend": h1_trend,

        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,

        "liquidity": liquidity_type,
        "candle": candle_type,
        "bos": bos,
        "in_zone": in_zone,

        "entry_low": entry_low,
        "entry_high": entry_high,

        "swing_low": swing_low,
        "swing_high": swing_high,

        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,

        "trigger": trigger,

        "reasons": reasons,
        "missing": missing,

        "source_15m": source_15m,
        "source_1h": source_1h,
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
            "Cuba semula beberapa saat lagi."
        )

    if asset == "gold":

        name = "GOLD (XAUUSD)"
        emoji = "🥇"

    else:

        name = "BTC"
        emoji = "₿"

    price = result["price"]

    direction = result[
        "direction"
    ]

    # ========================================================
    # HEADER
    # ========================================================

    message = (
        f"{emoji} *{name} SIGNAL V5.6*\n\n"
        f"💰 Harga: `${price:,.2f}`\n\n"
    )

    if direction == "BUY":

        message += (
            "🟢 *SIGNAL: BUY*\n"
            "📈 Entry confirmation lengkap\n\n"
        )

    elif direction == "SELL":

        message += (
            "🔴 *SIGNAL: SELL*\n"
            "📉 Entry confirmation lengkap\n\n"
        )

    else:

        message += (
            "🟡 *SIGNAL: WAIT*\n"
            "⏳ Tunggu confirmation\n\n"
        )

    # ========================================================
    # MARKET DATA
    # ========================================================

    message += (
        f"🧭 *Bias:* `{result['bias']}`\n"
        f"💯 *Confidence:* `{result['confidence']}%`\n"
        f"📐 *Structure:* `{result['structure']}`\n"
        f"🕐 *1H Trend:* `{result['h1_trend']}`\n"
        f"📊 *RSI:* `{result['rsi']:.1f}`\n"
        f"📈 *ADX:* `{result['adx']:.1f}`\n\n"
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
    # ENTRY TRIGGER
    # ========================================================

    if direction == "BUY":

        trigger_text = (
            "🟢 BUY ENTRY CONFIRMED"
        )

    elif direction == "SELL":

        trigger_text = (
            "🔴 SELL ENTRY CONFIRMED"
        )

    else:

        trigger_text = (
            "🟡 WAIT FOR ENTRY TRIGGER"
        )

    message += (
        "⏳ *ENTRY TRIGGER*\n"
        f"{trigger_text}\n\n"
    )

    # ========================================================
    # WATCH ZONE
    # ========================================================

    message += (
        "🟡 *WATCH ZONE*\n"
        f"`{result['entry_low']:,.2f}"
        f" – "
        f"{result['entry_high']:,.2f}`\n\n"
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
    # SL TP
    # ========================================================

    if direction != "WAIT":

        message += (
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

    if result["missing"]:

        message += (
            "\n⏳ *BELUM LENGKAP*\n"
        )

        for item in result[
            "missing"
        ]:

            message += (
                f"• Tunggu {item}\n"
            )

    # ========================================================
    # SOURCE
    # ========================================================

    message += (
        "\n📡 *DATA SOURCE*\n"
        f"15M: `{result['source_15m']}`\n"
        f"1H: `{result['source_1h']}`\n\n"

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
        "🤖 *GOLD & BTC SIGNAL BOT V5.6*\n\n"

        "📌 *COMMANDS*\n\n"

        "/price\n"
        "➡️ Harga Gold & BTC\n\n"

        "/signal gold\n"
        "➡️ Signal Gold\n\n"

        "/signal btc\n"
        "➡️ Signal BTC\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 Technical Engine V5.6\n"
        "📊 15M + 1H\n"
        "📐 Market Structure\n"
        "💧 Liquidity Sweep\n"
        "🕯 Candle Confirmation\n"
        "📐 Break of Structure\n"
        "🔄 Retest Entry Zone\n"
        "🎯 SL / TP\n"
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
        "📈 *HARGA SEMASA V5.6*\n\n"
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

    status = await update.message.reply_text(
        "🧠 *SIGNAL V5.6*\n\n"
        "📡 Mengambil candle...\n"
        "📊 15M + 1H\n"
        "💧 Checking liquidity...\n"
        "🕯 Checking candle...\n"
        "📐 Checking BOS...\n"
        "🔄 Checking retest...\n"
        "⏳ Sila tunggu...",
        parse_mode="Markdown"
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
        "📰 *NEWS MONITOR V5.6*\n\n"

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
    print(
        "=========================================="
    )
    print(
        "🤖 GOLD & BTC SIGNAL BOT V5.6"
    )
    print(
        "=========================================="
    )

    if not TOKEN:

        print(
            "❌ BOT_TOKEN TIDAK DIJUMPAI"
        )

        return

    print(
        "✅ BOT_TOKEN berjaya dibaca!"
    )

    print(
        "🤖 Starting V5.6..."
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
            "🚀 V5.6 BOT AKTIF!"
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
            "📊 15M + 1H"
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
