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
# GOLD & BTC SIGNAL BOT V6.0
# CLEAN + STRONGER CONFIRMATION ENGINE
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

SYMBOLS = {
    "gold": [
        "GC=F",
        "XAUUSD=X",
    ],
    "btc": [
        "BTC-USD",
    ],
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

SWING_LOOKBACK = 40
BOS_LOOKBACK = 10

ZONE_ATR = 0.25

SL_ATR = 1.20
TP1_ATR = 1.20
TP2_ATR = 2.00
TP3_ATR = 3.00

# Minimum entry score
ENTRY_THRESHOLD = 55

# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# ============================================================
# YAHOO CANDLES
# ============================================================

def yahoo_candles(
    symbol,
    interval="15m",
    range_value="5d",
):
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
        response = SESSION.get(
            url,
            params=params,
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

                if None in (
                    o,
                    h,
                    l,
                    c,
                ):
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
# GET CANDLES
# ============================================================

def get_candles(
    asset,
    interval,
    range_value,
):

    for symbol in SYMBOLS.get(
        asset,
        [],
    ):

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
# REMOVE CURRENT / INCOMPLETE CANDLE
# ============================================================

def closed_candles(candles):

    if len(candles) <= 2:
        return candles

    # Yahoo may return the currently forming candle.
    # We remove the newest candle for technical analysis.
    return candles[:-1]


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

        return (
            candles[-1]["close"],
            source,
        )

    if asset == "gold":

        try:

            response = SESSION.get(
                "https://api.gold-api.com/price/XAU",
                timeout=15,
            )

            if response.status_code == 200:

                data = response.json()

                price = data.get(
                    "price"
                )

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

def ema(
    values,
    period,
):

    if len(values) < period:
        return None

    multiplier = 2.0 / (
        period + 1
    )

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

def rsi(
    values,
    period=14,
):

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(
        1,
        len(values),
    ):

        change = (
            values[i]
            - values[i - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0.0)

        else:

            gains.append(0.0)
            losses.append(
                abs(change)
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
        len(gains),
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
        return 100.0

    rs = (
        avg_gain
        / avg_loss
    )

    return 100.0 - (
        100.0
        / (1.0 + rs)
    )


# ============================================================
# ATR
# ============================================================

def atr(
    candles,
    period=14,
):

    if len(candles) < period + 1:
        return None

    trs = []

    for i in range(
        1,
        len(candles),
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
    period=14,
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
        len(candles),
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
            ),
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
            plus_dm.append(0.0)

        if (
            low_diff > high_diff
            and low_diff > 0
        ):
            minus_dm.append(
                low_diff
            )
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

    for i in range(
        period,
        len(trs),
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
    candles,
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
    lookback=40,
):

    if len(candles) < 10:
        return None, None

    recent = candles[
        -lookback:
    ]

    swing_low = min(
        c["low"]
        for c in recent
    )

    swing_high = max(
        c["high"]
        for c in recent
    )

    return (
        swing_low,
        swing_high,
    )


# ============================================================
# LIQUIDITY SWEEP V6
# ============================================================

def detect_liquidity_sweep(
    candles,
    swing_low,
    swing_high,
):

    if len(candles) < 5:
        return "NONE"

    recent = candles[-5:]

    range_size = (
        swing_high
        - swing_low
    )

    if range_size <= 0:
        return "NONE"

    tolerance = (
        range_size * 0.0015
    )

    # Check latest 3 closed candles
    for c in reversed(
        recent[-3:]
    ):

        bullish = (
            c["low"]
            < swing_low
            and c["close"]
            > swing_low
            and c["close"]
            > c["open"]
        )

        bearish = (
            c["high"]
            > swing_high
            and c["close"]
            < swing_high
            and c["close"]
            < c["open"]
        )

        bullish_near = (
            c["low"]
            <= swing_low + tolerance
            and c["close"]
            > swing_low
            and c["close"]
            > c["open"]
        )

        bearish_near = (
            c["high"]
            >= swing_high - tolerance
            and c["close"]
            < swing_high
            and c["close"]
            < c["open"]
        )

        if bullish:
            return "BULLISH SWEEP"

        if bearish:
            return "BEARISH SWEEP"

        if bullish_near:
            return "BULLISH SWEEP"

        if bearish_near:
            return "BEARISH SWEEP"

    return "NONE"


# ============================================================
# CANDLE CONFIRMATION V6
# ============================================================

def candle_confirmation(
    candles,
):

    if len(candles) < 3:
        return "NONE"

    current = candles[-1]
    previous = candles[-2]

    bullish_engulfing = (
        current["close"]
        > current["open"]
        and previous["close"]
        < previous["open"]
        and current["open"]
        <= previous["close"]
        and current["close"]
        >= previous["open"]
    )

    bearish_engulfing = (
        current["close"]
        < current["open"]
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

    body = abs(
        current["close"]
        - current["open"]
    )

    candle_range = (
        current["high"]
        - current["low"]
    )

    if candle_range <= 0:
        return "NONE"

    body_ratio = (
        body / candle_range
    )

    upper_wick = (
        current["high"]
        - max(
            current["open"],
            current["close"],
        )
    )

    lower_wick = (
        min(
            current["open"],
            current["close"],
        )
        - current["low"]
    )

    if (
        current["close"]
        > current["open"]
        and body_ratio >= 0.60
        and lower_wick <= body
    ):
        return "BULLISH CANDLE"

    if (
        current["close"]
        < current["open"]
        and body_ratio >= 0.60
        and upper_wick <= body
    ):
        return "BEARISH CANDLE"

    return "NONE"


# ============================================================
# BOS V6
# ============================================================

def detect_bos(
    candles,
    direction,
    lookback=10,
):

    if len(candles) < (
        lookback + 3
    ):
        return "NONE"

    current = candles[-1]

    previous = candles[
        -lookback - 1:-1
    ]

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
# BOS LEVEL
# ============================================================

def bos_level(
    candles,
    direction,
    lookback=10,
):

    if len(candles) < (
        lookback + 2
    ):
        return None

    previous = candles[
        -lookback - 1:-1
    ]

    if direction == "BUY":

        return max(
            c["high"]
            for c in previous
        )

    if direction == "SELL":

        return min(
            c["low"]
            for c in previous
        )

    return None


# ============================================================
# RETEST V6
# ============================================================

def detect_retest(
    candles,
    level,
    direction,
    atr_value,
):

    if (
        len(candles) < 3
        or level is None
        or atr_value is None
    ):
        return "NONE"

    tolerance = (
        atr_value * 0.20
    )

    # Look at last 3 candles.
    for c in candles[-3:]:

        touched = (
            c["low"]
            <= level + tolerance
            and c["high"]
            >= level - tolerance
        )

        if not touched:
            continue

        if (
            direction == "BUY"
            and c["close"] > level
            and c["close"] > c["open"]
        ):
            return "BULLISH RETEST"

        if (
            direction == "SELL"
            and c["close"] < level
            and c["close"] < c["open"]
        ):
            return "BEARISH RETEST"

    return "NONE"


# ============================================================
# ENTRY SEQUENCE
# ============================================================

def entry_sequence(
    candles,
    bias,
    swing_low,
    swing_high,
    atr_value,
):

    liquidity = detect_liquidity_sweep(
        candles,
        swing_low,
        swing_high,
    )

    candle = candle_confirmation(
        candles
    )

    bos = detect_bos(
        candles,
        bias,
        BOS_LOOKBACK,
    )

    level = bos_level(
        candles,
        bias,
        BOS_LOOKBACK,
    )

    retest = detect_retest(
        candles,
        level,
        bias,
        atr_value,
    )

    score = 0
    reasons = []

    if bias == "BUY":

        if liquidity == "BULLISH SWEEP":
            score += 25
            reasons.append(
                "Bullish liquidity sweep"
            )

        if candle in (
            "BULLISH ENGULFING",
            "BULLISH CANDLE",
        ):
            score += 20
            reasons.append(
                candle
            )

        if bos == "BULLISH BOS":
            score += 30
            reasons.append(
                "Bullish BOS"
            )

        if retest == "BULLISH RETEST":
            score += 25
            reasons.append(
                "Bullish retest"
            )

    elif bias == "SELL":

        if liquidity == "BEARISH SWEEP":
            score += 25
            reasons.append(
                "Bearish liquidity sweep"
            )

        if candle in (
            "BEARISH ENGULFING",
            "BEARISH CANDLE",
        ):
            score += 20
            reasons.append(
                candle
            )

        if bos == "BEARISH BOS":
            score += 30
            reasons.append(
                "Bearish BOS"
            )

        if retest == "BEARISH RETEST":
            score += 25
            reasons.append(
                "Bearish retest"
            )

    complete = (
        score >= ENTRY_THRESHOLD
    )

    return {
        "liquidity": liquidity,
        "candle": candle,
        "bos": bos,
        "bos_level": level,
        "retest": retest,
        "score": score,
        "complete": complete,
        "reasons": reasons,
    }


# ============================================================
# ANALYZE ASSET V6
# ============================================================

def analyze_asset(asset):

    raw_15m, source_15m = get_candles(
        asset,
        "15m",
        "5d",
    )

    raw_1h, source_1h = get_candles(
        asset,
        "1h",
        "1mo",
    )

    if len(raw_15m) < (
        MIN_15M_CANDLES + 1
    ):

        logger.warning(
            "%s insufficient 15M data: %s",
            asset,
            len(raw_15m),
        )

        return None

    candles_15m = closed_candles(
        raw_15m
    )

    candles_1h = closed_candles(
        raw_1h
    )

    if len(candles_15m) < (
        MIN_15M_CANDLES
    ):
        return None

    closes = [
        c["close"]
        for c in candles_15m
    ]

    technical_price = closes[-1]

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

    swing_low, swing_high = (
        swing_levels(
            candles_15m,
            SWING_LOOKBACK,
        )
    )

    # ========================================================
    # 1H TREND
    # ========================================================

    h1_trend = "NEUTRAL"
    h1_structure = "NEUTRAL"

    if len(candles_1h) >= (
        MIN_H1_CANDLES
    ):

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

        h1_structure = market_structure(
            candles_1h
        )

    # ========================================================
    # BIAS SCORE
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
            50
            <= rsi_value
            <= 68
        ):

            buy_score += 15

            buy_reasons.append(
                "RSI menyokong BUY"
            )

        elif (
            32
            <= rsi_value
            < 50
        ):

            sell_score += 15

            sell_reasons.append(
                "RSI menyokong SELL"
            )

        elif rsi_value > 70:

            sell_score += 8

            sell_reasons.append(
                "RSI tinggi / risiko overbought"
            )

        elif rsi_value < 30:

            buy_score += 8

            buy_reasons.append(
                "RSI rendah / risiko oversold"
            )

    # 15M structure
    if structure == "BULLISH":

        buy_score += 20

        buy_reasons.append(
            "15M structure bullish"
        )

    elif structure == "BEARISH":

        sell_score += 20

        sell_reasons.append(
            "15M structure bearish"
        )

    # H1 trend
    if h1_trend == "BULLISH":

        buy_score += 20

        buy_reasons.append(
            "1H trend bullish"
        )

    elif h1_trend == "BEARISH":

        sell_score += 20

        sell_reasons.append(
            "1H trend bearish"
        )

    # H1 structure
    if h1_structure == "BULLISH":

        buy_score += 10

        buy_reasons.append(
            "1H structure bullish"
        )

    elif h1_structure == "BEARISH":

        sell_score += 10

        sell_reasons.append(
            "1H structure bearish"
        )

    # ADX
    if adx_value is not None:

        if adx_value >= 25:

            if buy_score > sell_score:

                buy_score += 10

                buy_reasons.append(
                    "ADX trend kuat"
                )

            elif sell_score > buy_score:

                sell_score += 10

                sell_reasons.append(
                    "ADX trend kuat"
                )

    # ========================================================
    # BIAS
    # ========================================================

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
    # ATR FALLBACK
    # ========================================================

    if (
        atr_value is None
        or atr_value <= 0
    ):

        atr_value = (
            technical_price
            * 0.005
        )

    # ========================================================
    # WATCH ZONE
    # ========================================================

    zone_size = (
        atr_value
        * ZONE_ATR
    )

    if bias == "BUY":

        watch_low = (
            technical_price
            - zone_size
        )

        watch_high = technical_price

    elif bias == "SELL":

        watch_low = technical_price

        watch_high = (
            technical_price
            + zone_size
        )

    else:

        watch_low = (
            technical_price
            - zone_size
        )

        watch_high = (
            technical_price
            + zone_size
        )

    # ========================================================
    # ENTRY ENGINE
    # ========================================================

    sequence = entry_sequence(
        candles_15m,
        bias,
        swing_low,
        swing_high,
        atr_value,
    )

    entry_score = sequence[
        "score"
    ]

    trigger_complete = sequence[
        "complete"
    ]

    if trigger_complete:

        direction = bias

    else:

        direction = "WAIT"

    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence = (
        base_confidence
        + int(
            entry_score * 0.35
        )
    )

    confidence = max(
        50,
        min(
            95,
            confidence,
        ),
    )

    # Weak ADX penalty
    if (
        adx_value is not None
        and adx_value < 20
    ):

        confidence = max(
            50,
            confidence - 10,
        )

    # Conflict penalty
    if (
        h1_structure != "NEUTRAL"
        and structure != "NEUTRAL"
        and h1_structure
        != structure
    ):

        confidence = max(
            50,
            confidence - 10,
        )

    # ========================================================
    # ENTRY / SL / TP
    # ========================================================

    live_price, live_source = (
        get_live_price(asset)
    )

    if live_price is None:

        display_price = (
            technical_price
        )

        price_source = source_15m

    else:

        display_price = live_price
        price_source = live_source

    if direction == "BUY":

        entry_price = (
            display_price
        )

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

        tp3 = (
            entry_price
            + atr_value * TP3_ATR
        )

    elif direction == "SELL":

        entry_price = (
            display_price
        )

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

        tp3 = (
            entry_price
            - atr_value * TP3_ATR
        )

    else:

        entry_price = None
        sl = None
        tp1 = None
        tp2 = None
        tp3 = None

    # ========================================================
    # ANALYSIS
    # ========================================================

    analysis = []

    if bias == "BUY":

        analysis.append(
            "Bias BUY"
        )

        analysis.extend(
            buy_reasons
        )

    elif bias == "SELL":

        analysis.append(
            "Bias SELL"
        )

        analysis.extend(
            sell_reasons
        )

    else:

        analysis.append(
            "Bias neutral"
        )

    analysis.extend(
        sequence["reasons"]
    )

    if not trigger_complete:

        if bias == "BUY":

            if (
                sequence["liquidity"]
                != "BULLISH SWEEP"
            ):

                analysis.append(
                    "Tunggu bullish liquidity sweep"
                )

            if sequence["candle"] not in (
                "BULLISH ENGULFING",
                "BULLISH CANDLE",
            ):

                analysis.append(
                    "Tunggu bullish candle confirmation"
                )

            if (
                sequence["bos"]
                != "BULLISH BOS"
            ):

                analysis.append(
                    "Tunggu bullish BOS"
                )

            if (
                sequence["retest"]
                != "BULLISH RETEST"
            ):

                analysis.append(
                    "Tunggu bullish retest"
                )

        elif bias == "SELL":

            if (
                sequence["liquidity"]
                != "BEARISH SWEEP"
            ):

                analysis.append(
                    "Tunggu bearish liquidity sweep"
                )

            if sequence["candle"] not in (
                "BEARISH ENGULFING",
                "BEARISH CANDLE",
            ):

                analysis.append(
                    "Tunggu bearish candle confirmation"
                )

            if (
                sequence["bos"]
                != "BEARISH BOS"
            ):

                analysis.append(
                    "Tunggu bearish BOS"
                )

            if (
                sequence["retest"]
                != "BEARISH RETEST"
            ):

                analysis.append(
                    "Tunggu bearish retest"
                )

    return {
        "price": display_price,
        "technical_price": technical_price,
        "price_source": price_source,

        "direction": direction,
        "bias": bias,

        "confidence": confidence,

        "buy_score": buy_score,
        "sell_score": sell_score,
        "entry_score": entry_score,

        "structure": structure,
        "h1_structure": h1_structure,
        "h1_trend": h1_trend,

        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,

        "liquidity": sequence[
            "liquidity"
        ],

        "candle": sequence[
            "candle"
        ],

        "bos": sequence[
            "bos"
        ],

        "retest": sequence[
            "retest"
        ],

        "bos_level": sequence[
            "bos_level"
        ],

        "watch_low": watch_low,
        "watch_high": watch_high,

        "swing_low": swing_low,
        "swing_high": swing_high,

        "entry_price": entry_price,

        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,

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
# FORMAT SIGNAL V6
# ============================================================

def format_signal(
    asset,
    result,
):

    if result is None:

        return (
            "❌ *DATA CANDLE GAGAL*\n\n"
            "15M candle tidak mencukupi.\n"
            "🔄 Cuba semula beberapa saat lagi."
        )

    if asset == "gold":

        name = "GOLD (XAUUSD)"
        emoji = "🥇"

    else:

        name = "BTC"
        emoji = "₿"

    direction = result[
        "direction"
    ]

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
        f"{emoji} *{name} SIGNAL V6.0*\n\n"

        f"💰 Harga: "
        f"`${fmt(result['price'])}`\n"
        f"📡 Price Source: "
        f"`{result['price_source']}`\n\n"

        f"{signal_text}\n\n"

        f"🧭 *BIAS:* "
        f"`{result['bias']}`\n"

        f"💯 *CONFIDENCE:* "
        f"`{result['confidence']}%`\n"

        f"📊 *BIAS SCORE:* "
        f"`BUY {result['buy_score']} / "
        f"SELL {result['sell_score']}`\n"

        f"🎯 *ENTRY SCORE:* "
        f"`{result['entry_score']}/100`\n\n"

        f"📐 *15M STRUCTURE:* "
        f"`{result['structure']}`\n"

        f"📐 *1H STRUCTURE:* "
        f"`{result['h1_structure']}`\n"

        f"🕐 *1H TREND:* "
        f"`{result['h1_trend']}`\n"

        f"📊 *RSI:* "
        f"`{rsi_text}`\n"

        f"📈 *ADX:* "
        f"`{adx_text}`\n\n"

        f"💧 *LIQUIDITY SWEEP*\n"
        f"`{result['liquidity']}`\n\n"

        f"🕯 *CANDLE CONFIRMATION*\n"
        f"`{result['candle']}`\n\n"

        f"📐 *BREAK OF STRUCTURE*\n"
        f"`{result['bos']}`\n\n"

        f"🔄 *RETEST*\n"
        f"`{result['retest']}`\n\n"
    )

    # ========================================================
    # ENTRY TRIGGER
    # ========================================================

    if direction == "BUY":

        trigger = (
            "🟢 *BUY ENTRY TRIGGER AKTIF*"
        )

    elif direction == "SELL":

        trigger = (
            "🔴 *SELL ENTRY TRIGGER AKTIF*"
        )

    else:

        if result["bias"] == "BUY":

            trigger = (
                "🟡 *WAIT FOR BUY TRIGGER*"
            )

        elif result["bias"] == "SELL":

            trigger = (
                "🟡 *WAIT FOR SELL TRIGGER*"
            )

        else:

            trigger = (
                "⚪ *WAIT / NO CLEAR BIAS*"
            )

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

    if result["bos_level"] is not None:

        message += (
            "📐 *BOS LEVEL*\n"
            f"`{fmt(result['bos_level'])}`\n\n"
        )

    # ========================================================
    # TRADE LEVELS
    # ========================================================

    if direction != "WAIT":

        message += (
            "🎯 *ENTRY*\n"
            f"`{fmt(result['entry_price'])}`\n\n"

            "🛑 *STOP LOSS*\n"
            f"`{fmt(result['sl'])}`\n\n"

            "🎯 *TP1*\n"
            f"`{fmt(result['tp1'])}`\n\n"

            "🎯 *TP2*\n"
            f"`{fmt(result['tp2'])}`\n\n"

            "🎯 *TP3*\n"
            f"`{fmt(result['tp3'])}`\n\n"
        )

    # ========================================================
    # ANALYSIS
    # ========================================================

    message += (
        "🧠 *ANALYSIS V6*\n"
    )

    unique_analysis = []

    for item in result[
        "analysis"
    ]:

        if item not in unique_analysis:

            unique_analysis.append(
                item
            )

    for item in unique_analysis:

        message += (
            f"• {item}\n"
        )

    # ========================================================
    # DATA
    # ========================================================

    message += (
        "\n📡 *DATA SOURCE*\n"
        f"15M: `{result['source_15m']}`\n"
        f"1H: `{result['source_1h']}`\n\n"

        "🧠 Engine: "
        "`V6.0 CLOSED-CANDLE`\n"

        "📊 Timeframe: "
        "`15M + 1H`\n"

        "💧 Liquidity: "
        "`ON`\n"

        "📐 BOS: "
        "`ON`\n"

        "🔄 Retest: "
        "`ON`\n"

        "🎯 ATR SL/TP: "
        "`ON`\n\n"

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
        "🤖 *GOLD & BTC SIGNAL BOT V6.0*\n\n"

        "📌 *COMMANDS*\n\n"

        "/price\n"
        "➡️ Harga Gold & BTC\n\n"

        "/signal gold\n"
        "➡️ Signal Gold\n\n"

        "/signal btc\n"
        "➡️ Signal BTC\n\n"

        "/signal all\n"
        "➡️ Gold + BTC\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 *V6 ENGINE*\n"
        "📊 Closed Candle\n"
        "📊 15M + 1H\n"
        "📐 Market Structure\n"
        "📈 EMA20 / EMA50\n"
        "📊 RSI\n"
        "📈 ADX\n"
        "📏 ATR\n"
        "💧 Liquidity Sweep\n"
        "🕯 Candle Confirmation\n"
        "📐 BOS\n"
        "🔄 Retest\n"
        "🎯 Entry / SL / TP1 / TP2 / TP3\n"
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

    gold, gold_source = (
        get_live_price("gold")
    )

    btc, btc_source = (
        get_live_price("btc")
    )

    text = (
        "📈 *HARGA SEMASA V6.0*\n\n"
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
# SINGLE SIGNAL
# ============================================================

async def run_single_signal(
    update,
    asset,
):

    status = await update.message.reply_text(
        "🧠 *SIGNAL V6.0*\n\n"
        "📡 Mengambil market data...\n"
        "📊 Loading 15M...\n"
        "🕐 Loading 1H...\n"
        "📈 EMA / RSI / ADX / ATR...\n"
        "💧 Checking liquidity...\n"
        "🕯 Checking candle...\n"
        "📐 Checking BOS...\n"
        "🔄 Checking retest...\n"
        "⏳ Sila tunggu...",
        parse_mode="Markdown",
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
# SIGNAL COMMAND
# ============================================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_text(
            "❌ Pilih asset:\n\n"
            "/signal gold\n"
            "/signal btc\n"
            "/signal all"
        )

        return

    asset = (
        context.args[0]
        .lower()
        .strip()
    )

    if asset == "all":

        await run_single_signal(
            update,
            "gold",
        )

        await run_single_signal(
            update,
            "btc",
        )

        return

    if asset not in (
        "gold",
        "btc",
    ):

        await update.message.reply_text(
            "❌ Asset tidak disokong.\n\n"
            "/signal gold\n"
            "/signal btc\n"
            "/signal all"
        )

        return

    await run_single_signal(
        update,
        asset,
    )


# ============================================================
# NEWS
# ============================================================

async def news(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "📰 *NEWS MONITOR V6.0*\n\n"

        "🥇 *GOLD*\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• US CPI\n"
        "• NFP\n"
        "• Interest Rate\n"
        "• US Bond Yields\n\n"

        "₿ *BITCOIN*\n"
        "• ETF Flow\n"
        "• Funding Rate\n"
        "• BTC Dominance\n"
        "• US Macro Data\n"
        "• Risk Sentiment\n\n"

        "⚠️ News engine V6 belum mengambil "
        "berita live. Jangan anggap bahagian "
        "ini sebagai pengesahan news."
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
    print("🤖 GOLD & BTC SIGNAL BOT V6.0")
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
            "🚀 V6.0 BOT AKTIF!"
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
            "📊 15M + 1H CLOSED CANDLES"
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
            "🎯 ATR SL/TP"
        )

        print(
            "🚫 NO AUTO TRADING"
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
    main()# SETTINGS
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
    main()
