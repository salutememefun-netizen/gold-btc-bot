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
# GOLD & BTC SIGNAL BOT V7
# FULL VERSION - READY FOR RAILWAY
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
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
})


# ============================================================
# YAHOO REQUEST
# ============================================================

def yahoo_request(
    symbol,
    interval="15m",
    range_value="5d",
):
    """
    Cuba beberapa Yahoo Finance endpoint.
    """

    endpoints = [
        "https://query1.finance.yahoo.com",
        "https://query2.finance.yahoo.com",
    ]

    params = {
        "interval": interval,
        "range": range_value,
        "includePrePost": "true",
        "events": "div,splits",
    }

    for endpoint in endpoints:

        url = (
            f"{endpoint}/v8/finance/chart/"
            f"{symbol}"
        )

        try:

            response = SESSION.get(
                url,
                params=params,
                timeout=20,
            )

            if response.status_code != 200:
                logger.warning(
                    "%s returned HTTP %s",
                    symbol,
                    response.status_code,
                )
                continue

            data = response.json()

            result = (
                data
                .get("chart", {})
                .get("result")
            )

            if result:
                return result[0]

        except Exception as e:

            logger.warning(
                "Yahoo request error %s: %s",
                symbol,
                e,
            )

    return None


# ============================================================
# YAHOO CANDLES
# ============================================================

def yahoo_candles(
    symbol,
    interval="15m",
    range_value="5d",
):

    result = yahoo_request(
        symbol,
        interval,
        range_value,
    )

    if not result:
        return []

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

    for i in range(len(timestamps)):

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
                "time": timestamps[i],
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


# ============================================================
# LIVE PRICE
# ============================================================

def get_live_price(asset):

    for symbol in SYMBOLS.get(
        asset,
        [],
    ):

        # ----------------------------------------------------
        # METHOD 1
        # Yahoo metadata
        # ----------------------------------------------------

        result = yahoo_request(
            symbol,
            "1m",
            "1d",
        )

        if result:

            meta = result.get(
                "meta",
                {},
            )

            possible_prices = [
                meta.get(
                    "regularMarketPrice"
                ),
                meta.get(
                    "previousClose"
                ),
            ]

            for price in possible_prices:

                if price is not None:

                    try:

                        return (
                            float(price),
                            symbol,
                            "Yahoo Market Price",
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

        # ----------------------------------------------------
        # METHOD 2
        # 1M candle
        # ----------------------------------------------------

        candles = yahoo_candles(
            symbol,
            "1m",
            "1d",
        )

        if candles:

            price = candles[-1].get(
                "close"
            )

            if price is not None:

                return (
                    float(price),
                    symbol,
                    "Yahoo 1M Candle",
                )

        # ----------------------------------------------------
        # METHOD 3
        # 15M candle fallback
        # ----------------------------------------------------

        candles = yahoo_candles(
            symbol,
            "15m",
            "5d",
        )

        if candles:

            price = candles[-1].get(
                "close"
            )

            if price is not None:

                return (
                    float(price),
                    symbol,
                    "Yahoo 15M Candle",
                )

    return None, None, None


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
                "%s %s = %s candles [%s]",
                asset,
                interval,
                len(candles),
                symbol,
            )

            return (
                candles,
                symbol,
            )

    return [], None


# ============================================================
# EMA
# ============================================================

def ema(
    values,
    period,
):

    if len(values) < period:
        return None

    multiplier = (
        2 / (period + 1)
    )

    value = (
        sum(values[:period])
        / period
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

        if avg_gain == 0:
            return 50.0

        return 100.0

    rs = (
        avg_gain
        / avg_loss
    )

    return (
        100
        - (
            100
            / (1 + rs)
        )
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
# SWINGS
# ============================================================

def get_swings(
    candles,
    lookback=30,
):

    if not candles:
        return None, None

    lookback = min(
        lookback,
        len(candles),
    )

    recent = candles[
        -lookback:
    ]

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
        swing_high,
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
# CANDLE CONFIRMATION
# ============================================================

def candle_confirmation(
    candles,
):

    if len(candles) < 3:
        return "NONE"

    prev = candles[-2]
    cur = candles[-1]

    prev_bearish = (
        prev["close"]
        < prev["open"]
    )

    prev_bullish = (
        prev["close"]
        > prev["open"]
    )

    cur_bullish = (
        cur["close"]
        > cur["open"]
    )

    cur_bearish = (
        cur["close"]
        < cur["open"]
    )

    # Bullish engulfing

    if (
        prev_bearish
        and cur_bullish
        and cur["open"]
        <= prev["close"]
        and cur["close"]
        >= prev["open"]
    ):

        return "BULLISH ENGULFING"

    # Bearish engulfing

    if (
        prev_bullish
        and cur_bearish
        and cur["open"]
        >= prev["close"]
        and cur["close"]
        <= prev["open"]
    ):

        return "BEARISH ENGULFING"

    body = abs(
        cur["close"]
        - cur["open"]
    )

    candle_range = (
        cur["high"]
        - cur["low"]
    )

    if candle_range > 0:

        ratio = (
            body
            / candle_range
        )

        if (
            cur_bullish
            and ratio >= 0.65
        ):

            return "BULLISH CANDLE"

        if (
            cur_bearish
            and ratio >= 0.65
        ):

            return "BEARISH CANDLE"

    return "NONE"


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def liquidity_sweep(
    candles,
):

    if len(candles) < 12:
        return "NONE", None

    current = candles[-1]

    previous = candles[-6:-1]

    liquidity_high = max(
        c["high"]
        for c in previous
    )

    liquidity_low = min(
        c["low"]
        for c in previous
    )

    # Sell-side sweep

    if (
        current["low"]
        < liquidity_low
        and current["close"]
        > liquidity_low
    ):

        return (
            "BULLISH SWEEP",
            liquidity_low,
        )

    # Buy-side sweep

    if (
        current["high"]
        > liquidity_high
        and current["close"]
        < liquidity_high
    ):

        return (
            "BEARISH SWEEP",
            liquidity_high,
        )

    return "NONE", None


# ============================================================
# BOS
# ============================================================

def detect_bos(
    candles,
):

    if len(candles) < 15:
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

    if (
        current["close"]
        > previous_high
    ):

        return "BULLISH BOS"

    if (
        current["close"]
        < previous_low
    ):

        return "BEARISH BOS"

    return "NONE"


# ============================================================
# RETEST
# ============================================================

def detect_retest(
    candles,
    bos,
    atr_value,
):

    if (
        bos == "NONE"
        or atr_value is None
    ):

        return "NONE", None

    if len(candles) < 8:
        return "NONE", None

    current = candles[-1]

    previous = candles[-7:-1]

    previous_high = max(
        c["high"]
        for c in previous
    )

    previous_low = min(
        c["low"]
        for c in previous
    )

    tolerance = (
        atr_value
        * 0.20
    )

    if bos == "BULLISH BOS":

        level = previous_high

        if (
            current["low"]
            <= level + tolerance
            and current["close"]
            > level
        ):

            return (
                "BULLISH RETEST",
                level,
            )

    if bos == "BEARISH BOS":

        level = previous_low

        if (
            current["high"]
            >= level - tolerance
            and current["close"]
            < level
        ):

            return (
                "BEARISH RETEST",
                level,
            )

    return "NONE", None


# ============================================================
# BIAS
# ============================================================

def calculate_bias(
    ema20,
    ema50,
    structure,
    h1_trend,
    rsi_value,
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
        buy += 2

    elif h1_trend == "BEARISH":
        sell += 2

    if rsi_value is not None:

        if (
            50
            <= rsi_value
            < 70
        ):

            buy += 1

        elif (
            30
            < rsi_value
            < 50
        ):

            sell += 1

    if buy > sell:
        return "BUY", buy, sell

    if sell > buy:
        return "SELL", buy, sell

    return "NEUTRAL", buy, sell


# ============================================================
# ENTRY ZONE
# ============================================================

def build_entry_zone(
    price,
    atr_value,
    direction,
    sweep_price=None,
    bos_price=None,
):

    if (
        atr_value is None
        or atr_value <= 0
    ):

        atr_value = (
            price
            * 0.005
        )

    reference = (
        bos_price
        if bos_price is not None
        else sweep_price
    )

    if reference is None:
        reference = price

    zone = (
        atr_value
        * 0.20
    )

    return (
        reference - zone,
        reference + zone,
    )


# ============================================================
# ANALYZE ASSET
# ============================================================

def analyze_asset(
    asset,
):

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

    if len(candles_15m) < 60:

        logger.warning(
            "%s only %s candles",
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
        20,
    )

    ema50 = ema(
        closes,
        50,
    )

    rsi_value = rsi(
        closes,
        14,
    )

    atr_value = atr(
        candles_15m,
        14,
    )

    adx_value = adx(
        candles_15m,
        14,
    )

    structure = market_structure(
        candles_15m
    )

    swing_low, swing_high = get_swings(
        candles_15m,
        30,
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
            20,
        )

        h1_ema50 = ema(
            h1_closes,
            50,
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

    (
        bias,
        buy_points,
        sell_points,
    ) = calculate_bias(
        ema20,
        ema50,
        structure,
        h1_trend,
        rsi_value,
    )

    # ========================================================
    # LIQUIDITY
    # ========================================================

    (
        liquidity,
        liquidity_price,
    ) = liquidity_sweep(
        candles_15m
    )

    # ========================================================
    # CANDLE
    # ========================================================

    candle_confirm = candle_confirmation(
        candles_15m
    )

    # ========================================================
    # BOS
    # ========================================================

    bos = detect_bos(
        candles_15m
    )

    bos_price = None

    if bos == "BULLISH BOS":

        previous = candles_15m[-11:-1]

        bos_price = max(
            c["high"]
            for c in previous
        )

    elif bos == "BEARISH BOS":

        previous = candles_15m[-11:-1]

        bos_price = min(
            c["low"]
            for c in previous
        )

    # ========================================================
    # RETEST
    # ========================================================

    (
        retest,
        retest_price,
    ) = detect_retest(
        candles_15m,
        bos,
        atr_value,
    )

    # ========================================================
    # TRIGGER SCORE
    # ========================================================

    trigger_score = 0

    if bias == "BUY":

        if liquidity == "BULLISH SWEEP":
            trigger_score += 25

        if candle_confirm in (
            "BULLISH ENGULFING",
            "BULLISH CANDLE",
        ):
            trigger_score += 20

        if bos == "BULLISH BOS":
            trigger_score += 25

        if retest == "BULLISH RETEST":
            trigger_score += 30

    elif bias == "SELL":

        if liquidity == "BEARISH SWEEP":
            trigger_score += 25

        if candle_confirm in (
            "BEARISH ENGULFING",
            "BEARISH CANDLE",
        ):
            trigger_score += 20

        if bos == "BEARISH BOS":
            trigger_score += 25

        if retest == "BEARISH RETEST":
            trigger_score += 30

    # ========================================================
    # FINAL SIGNAL
    # ========================================================

    direction = "WAIT"

    if (
        bias == "BUY"
        and trigger_score >= 70
        and liquidity == "BULLISH SWEEP"
        and candle_confirm in (
            "BULLISH ENGULFING",
            "BULLISH CANDLE",
        )
        and bos == "BULLISH BOS"
    ):

        direction = "BUY"

    elif (
        bias == "SELL"
        and trigger_score >= 70
        and liquidity == "BEARISH SWEEP"
        and candle_confirm in (
            "BEARISH ENGULFING",
            "BEARISH CANDLE",
        )
        and bos == "BEARISH BOS"
    ):

        direction = "SELL"

    # ========================================================
    # CONFIDENCE
    # ========================================================

    base_confidence = max(
        buy_points,
        sell_points,
    )

    confidence = min(
        95,
        50
        + (
            base_confidence
            * 7
        )
        + int(
            trigger_score
            * 0.25
        ),
    )

    if direction == "WAIT":
        confidence = min(
            confidence,
            69,
        )

    # ========================================================
    # SAFE ATR
    # ========================================================

    safe_atr = atr_value

    if (
        safe_atr is None
        or safe_atr <= 0
    ):

        safe_atr = (
            price
            * 0.005
        )

    # ========================================================
    # ENTRY
    # ========================================================

    (
        entry_low,
        entry_high,
    ) = build_entry_zone(
        price,
        safe_atr,
        bias,
        liquidity_price,
        bos_price,
    )

    # ========================================================
    # SL / TP
    # ========================================================

    sl = None
    tp1 = None
    tp2 = None

    if direction == "BUY":

        protective_level = (
            liquidity_price
            if liquidity_price is not None
            else swing_low
        )

        if protective_level is None:

            protective_level = (
                price
                - safe_atr
            )

        sl = (
            protective_level
            - (
                safe_atr
                * 0.30
            )
        )

        risk = (
            price
            - sl
        )

        if risk <= 0:

            risk = safe_atr

            sl = (
                price
                - risk
            )

        tp1 = (
            price
            + (
                risk
                * 1.5
            )
        )

        tp2 = (
            price
            + (
                risk
                * 2.5
            )
        )

    elif direction == "SELL":

        protective_level = (
            liquidity_price
            if liquidity_price is not None
            else swing_high
        )

        if protective_level is None:

            protective_level = (
                price
                + safe_atr
            )

        sl = (
            protective_level
            + (
                safe_atr
                * 0.30
            )
        )

        risk = (
            sl
            - price
        )

        if risk <= 0:

            risk = safe_atr

            sl = (
                price
                + risk
            )

        tp1 = (
            price
            - (
                risk
                * 1.5
            )
        )

        tp2 = (
            price
            - (
                risk
                * 2.5
            )
        )

    # ========================================================
    # REASONS
    # ========================================================

    reasons = []

    if bias == "BUY":
        reasons.append("Bias BUY")

    elif bias == "SELL":
        reasons.append("Bias SELL")

    if liquidity != "NONE":
        reasons.append(liquidity)

    if candle_confirm != "NONE":
        reasons.append(candle_confirm)

    if bos != "NONE":
        reasons.append(bos)

    if retest != "NONE":
        reasons.append(retest)

    if not reasons:
        reasons.append(
            "Belum ada confirmation"
        )

    # ========================================================
    # MISSING
    # ========================================================

    missing = []

    if bias == "BUY":

        if liquidity != "BULLISH SWEEP":

            missing.append(
                "Bullish liquidity sweep"
            )

        if candle_confirm not in (
            "BULLISH ENGULFING",
            "BULLISH CANDLE",
        ):

            missing.append(
                "Bullish candle confirmation"
            )

        if bos != "BULLISH BOS":

            missing.append(
                "Bullish BOS"
            )

        if retest != "BULLISH RETEST":

            missing.append(
                "Retest"
            )

    elif bias == "SELL":

        if liquidity != "BEARISH SWEEP":

            missing.append(
                "Bearish liquidity sweep"
            )

        if candle_confirm not in (
            "BEARISH ENGULFING",
            "BEARISH CANDLE",
        ):

            missing.append(
                "Bearish candle confirmation"
            )

        if bos != "BEARISH BOS":

            missing.append(
                "Bearish BOS"
            )

        if retest != "BEARISH RETEST":

            missing.append(
                "Retest"
            )

    else:

        missing.append(
            "Directional bias"
        )

    return {
        "price": price,
        "direction": direction,
        "bias": bias,
        "confidence": confidence,
        "buy_points": buy_points,
        "sell_points": sell_points,
        "trigger_score": trigger_score,
        "structure": structure,
        "h1_trend": h1_trend,
        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,
        "liquidity": liquidity,
        "liquidity_price": liquidity_price,
        "candle_confirmation": candle_confirm,
        "bos": bos,
        "bos_price": bos_price,
        "retest": retest,
        "retest_price": retest_price,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "reasons": reasons,
        "missing": missing,
        "source_15m": source_15m,
        "source_1h": source_1h,
    }


# ============================================================
# FORMAT PRICE
# ============================================================

def format_price(
    value,
    asset,
):

    if value is None:
        return "N/A"

    if asset == "btc":

        return (
            f"${value:,.2f}"
        )

    return (
        f"${value:,.2f}"
    )


# ============================================================
# FORMAT SIGNAL
# ============================================================

def format_signal(
    asset,
    result,
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

        name = "BITCOIN (BTC)"
        emoji = "₿"

    price = result["price"]

    direction = result["direction"]
    bias = result["bias"]

    confidence = result[
        "confidence"
    ]

    rsi_value = result["rsi"]
    adx_value = result["adx"]

    if rsi_value is None:
        rsi_text = "N/A"
    else:
        rsi_text = f"{rsi_value:.1f}"

    if adx_value is None:
        adx_text = "N/A"
    else:
        adx_text = f"{adx_value:.1f}"

    message = (
        f"{emoji} *{name} SIGNAL V7*\n\n"
        f"💰 Harga: `${price:,.2f}`\n"
    )

    if direction == "BUY":

        message += (
            "\n🟢 *SIGNAL: BUY*\n"
            "🚀 Entry trigger lengkap\n"
        )

    elif direction == "SELL":

        message += (
            "\n🔴 *SIGNAL: SELL*\n"
            "🚀 Entry trigger lengkap\n"
        )

    else:

        message += (
            "\n🟡 *SIGNAL: WAIT*\n"
            "⏳ Tunggu confirmation\n"
        )

    message += (
        f"\n🧭 *Bias:* `{bias}`\n"
        f"💯 *Confidence:* `{confidence}%`\n"
        f"🎯 *Trigger Score:* "
        f"`{result['trigger_score']}/100`\n"
        f"📐 *Structure:* "
        f"`{result['structure']}`\n"
        f"🕐 *1H Trend:* "
        f"`{result['h1_trend']}`\n"
        f"📊 *RSI:* `{rsi_text}`\n"
        f"📈 *ADX:* `{adx_text}`\n\n"
    )

    message += (
        "💧 *LIQUIDITY*\n"
        f"`{result['liquidity']}`\n\n"
    )

    message += (
        "🕯 *CANDLE CONFIRMATION*\n"
        f"`{result['candle_confirmation']}`\n\n"
    )

    message += (
        "📐 *BREAK OF STRUCTURE*\n"
        f"`{result['bos']}`\n\n"
    )

    message += (
        "🔄 *RETEST*\n"
        f"`{result['retest']}`\n\n"
    )

    if direction == "BUY":

        trigger_text = (
            "🟢 BUY TRIGGER ACTIVE"
        )

    elif direction == "SELL":

        trigger_text = (
            "🔴 SELL TRIGGER ACTIVE"
        )

    else:

        if bias == "BUY":

            if (
                result["liquidity"]
                != "BULLISH SWEEP"
            ):

                trigger_text = (
                    "🟡 WAIT FOR "
                    "BULLISH SWEEP"
                )

            elif (
                result["bos"]
                != "BULLISH BOS"
            ):

                trigger_text = (
                    "🟡 WAIT FOR "
                    "BULLISH BOS"
                )

            elif (
                result["retest"]
                != "BULLISH RETEST"
            ):

                trigger_text = (
                    "🟡 WAIT FOR "
                    "BULLISH RETEST"
                )

            else:

                trigger_text = (
                    "🟡 WAIT FOR "
                    "CONFIRMATION"
                )

        elif bias == "SELL":

            if (
                result["liquidity"]
                != "BEARISH SWEEP"
            ):

                trigger_text = (
                    "🟡 WAIT FOR "
                    "BEARISH SWEEP"
                )

            elif (
                result["bos"]
                != "BEARISH BOS"
            ):

                trigger_text = (
                    "🟡 WAIT FOR "
                    "BEARISH BOS"
                )

            elif (
                result["retest"]
                != "BEARISH RETEST"
            ):

                trigger_text = (
                    "🟡 WAIT FOR "
                    "BEARISH RETEST"
                )

            else:

                trigger_text = (
                    "🟡 WAIT FOR "
                    "CONFIRMATION"
                )

        else:

            trigger_text = (
                "🟡 WAIT FOR DIRECTION"
            )

    message += (
        "⏳ *ENTRY TRIGGER*\n"
        f"{trigger_text}\n\n"
    )

    message += (
        "🟡 *ENTRY / WATCH ZONE*\n"
        f"`{result['entry_low']:,.2f}"
        f" – "
        f"{result['entry_high']:,.2f}`\n\n"
    )

    if (
        result["swing_low"]
        is not None
    ):

        message += (
            "📉 *SWING LOW*\n"
            f"`{result['swing_low']:,.2f}`\n\n"
        )

    if (
        result["swing_high"]
        is not None
    ):

        message += (
            "📈 *SWING HIGH*\n"
            f"`{result['swing_high']:,.2f}`\n\n"
        )

    if direction != "WAIT":

        message += (
            "🛑 *STOP LOSS*\n"
            f"`{result['sl']:,.2f}`\n\n"

            "🎯 *TP1*\n"
            f"`{result['tp1']:,.2f}`\n\n"

            "🎯 *TP2*\n"
            f"`{result['tp2']:,.2f}`\n\n"
        )

    message += (
        "🧠 *ANALYSIS*\n"
    )

    for reason in result[
        "reasons"
    ]:

        message += (
            f"• {reason}\n"
        )

    if direction == "WAIT":

        message += (
            "\n⏳ *BELUM LENGKAP*\n"
        )

        for item in result[
            "missing"
        ]:

            message += (
                f"• Tunggu {item}\n"
            )

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
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "🤖 *GOLD & BTC SIGNAL BOT V7*\n\n"

        "📌 *COMMANDS*\n\n"

        "/price\n"
        "➡️ Harga Gold & BTC\n\n"

        "/signal gold\n"
        "➡️ Signal Gold\n\n"

        "/signal btc\n"
        "➡️ Signal Bitcoin\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 *TECHNICAL ENGINE V7*\n"
        "📊 15M + 1H\n"
        "📈 EMA 20/50\n"
        "📊 RSI\n"
        "📈 ADX\n"
        "📐 ATR\n"
        "🏗 Market Structure\n"
        "💧 Liquidity Sweep\n"
        "🕯 Candle Confirmation\n"
        "📐 BOS\n"
        "🔄 Retest\n"
        "🎯 Entry Zone\n"
        "🛑 SL\n"
        "🎯 TP1 / TP2\n\n"

        "🚫 Tiada auto-trading"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# ============================================================
# PRICE COMMAND
# ============================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    status = await update.message.reply_text(
        "📡 *MENGAMBIL HARGA...*\n\n"
        "🥇 Checking Gold...\n"
        "₿ Checking Bitcoin...",
        parse_mode="Markdown",
    )

    try:

        gold, gold_source, gold_method = (
            get_live_price("gold")
        )

        btc, btc_source, btc_method = (
            get_live_price("btc")
        )

        text = (
            "📈 *HARGA SEMASA V7*\n\n"
        )

        if gold is not None:

            text += (
                "🥇 *Gold XAUUSD*\n"
                f"`${gold:,.2f}`\n"
                f"Symbol: `{gold_source}`\n"
                f"Data: `{gold_method}`\n\n"
            )

        else:

            text += (
                "🥇 *Gold XAUUSD*\n"
                "❌ Gagal mendapatkan data\n\n"
            )

        if btc is not None:

            text += (
                "₿ *Bitcoin BTC*\n"
                f"`${btc:,.2f}`\n"
                f"Symbol: `{btc_source}`\n"
                f"Data: `{btc_method}`\n\n"
            )

        else:

            text += (
                "₿ *Bitcoin BTC*\n"
                "❌ Gagal mendapatkan data\n\n"
            )

        text += (
            "📡 Data: Yahoo Finance\n"
            "⚠️ Harga mungkin berbeza "
            "daripada broker MT5."
        )

        await status.edit_text(
            text,
            parse_mode="Markdown",
        )

    except Exception as e:

        logger.exception(
            "Price error"
        )

        await status.edit_text(
            "❌ *PRICE ERROR*\n\n"
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
            "/signal btc"
        )

        return

    asset = (
        context.args[0]
        .lower()
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
        "🧠 *SIGNAL V7*\n\n"
        "📡 Mengambil market data...\n"
        "📊 Analysing 15M...\n"
        "🕐 Analysing 1H...\n"
        "💧 Checking liquidity...\n"
        "🕯 Checking candle...\n"
        "📐 Checking BOS...\n"
        "🔄 Checking retest...\n"
        "🎯 Calculating SL/TP...\n\n"
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
# NEWS
# ============================================================

async def news(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "📰 *NEWS MONITOR V7*\n\n"

        "🥇 *GOLD*\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• US CPI\n"
        "• NFP\n"
        "• Interest Rate\n"
        "• US Jobs Data\n\n"

        "₿ *BITCOIN*\n"
        "• ETF Flow\n"
        "• Funding Rate\n"
        "• BTC Dominance\n"
        "• US Macro Data\n"
        "• Federal Reserve\n\n"

        "⚠️ News engine live belum "
        "disambungkan."
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
        "Telegram error:",
        exc_info=context.error,
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
        "🤖 GOLD & BTC SIGNAL BOT V7"
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
            "Railway Variables:"
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
        "🚀 Starting V7..."
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
            "🚀 V7 BOT AKTIF!"
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
            "🎯 Entry Zone / SL / TP"
        )

        print(
            "🚫 No Auto Trading"
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
