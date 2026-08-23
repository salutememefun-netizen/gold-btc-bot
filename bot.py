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
# GOLD & BTC SIGNAL BOT V5.7
# FLOW:
# WATCH -> LIQUIDITY SWEEP -> CANDLE CONFIRMATION
# -> BOS -> RETEST -> ENTRY READY
#
# NO AUTO TRADING
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
                "User-Agent":
                "Mozilla/5.0 (Android 10; Mobile)"
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
            data.get("chart", {})
            .get("result")
        )

        if not result:
            return []

        result = result[0]

        timestamps = result.get("timestamp", [])

        quotes = (
            result.get("indicators", {})
            .get("quote", [])
        )

        if not quotes:
            return []

        quote = quotes[0]

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
                f"from {symbol}"
            )

            return candles, symbol

    return [], None


# ============================================================
# PRICE
# ============================================================

def get_live_price(asset):

    candles, source = get_candles(
        asset,
        "1m",
        "1d"
    )

    if candles:
        return candles[-1]["close"], source

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

    value = sum(
        values[:period]
    ) / period

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
                + gains[i]
            )
            / period
        )

        avg_loss = (
            (
                avg_loss * (period - 1)
                + losses[i]
            )
            / period
        )

    if avg_loss == 0:
        return 100.0

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

    value = (
        sum(trs[:period])
        / period
    )

    for tr in trs[period:]:

        value = (
            (
                value * (period - 1)
                + tr
            )
            / period
        )

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
                + trs[i]
            )
            / period
        )

        plus_avg = (
            (
                plus_avg * (period - 1)
                + plus_dm[i]
            )
            / period
        )

        minus_avg = (
            (
                minus_avg * (period - 1)
                + minus_dm[i]
            )
            / period
        )

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

        dx_values.append(
            100
            * abs(
                plus_di - minus_di
            )
            / total
        )

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
        lookback = len(candles)

    recent = candles[-lookback:]

    swing_high = max(
        c["high"] for c in recent
    )

    swing_low = min(
        c["low"] for c in recent
    )

    return swing_low, swing_high


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def liquidity_sweep(candles, lookback=20):

    if len(candles) < lookback + 3:

        return {
            "type": "NONE",
            "level": None
        }

    previous = candles[
        -(lookback + 1):-1
    ]

    last = candles[-1]

    previous_low = min(
        c["low"] for c in previous
    )

    previous_high = max(
        c["high"] for c in previous
    )

    # Bullish liquidity sweep:
    # wick below old low, close back above
    if (
        last["low"] < previous_low
        and last["close"] > previous_low
    ):

        return {
            "type": "BULLISH SWEEP",
            "level": previous_low
        }

    # Bearish liquidity sweep:
    # wick above old high, close back below
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

    if len(candles) < 3:
        return "NONE"

    previous = candles[-2]
    current = candles[-1]

    # Bullish engulfing
    bullish_engulfing = (
        previous["close"]
        < previous["open"]
        and current["close"]
        > current["open"]
        and current["open"]
        <= previous["close"]
        and current["close"]
        >= previous["open"]
    )

    if bullish_engulfing:
        return "BULLISH ENGULFING"

    # Bearish engulfing
    bearish_engulfing = (
        previous["close"]
        > previous["open"]
        and current["close"]
        < current["open"]
        and current["open"]
        >= previous["close"]
        and current["close"]
        <= previous["open"]
    )

    if bearish_engulfing:
        return "BEARISH ENGULFING"

    # Strong bullish candle
    current_range = (
        current["high"]
        - current["low"]
    )

    if current_range > 0:

        bullish_body = (
            current["close"]
            - current["open"]
        )

        bearish_body = (
            current["open"]
            - current["close"]
        )

        if (
            bullish_body > 0
            and bullish_body
            / current_range >= 0.60
        ):
            return "BULLISH CANDLE"

        if (
            bearish_body > 0
            and bearish_body
            / current_range >= 0.60
        ):
            return "BEARISH CANDLE"

    return "NONE"


# ============================================================
# BREAK OF STRUCTURE
# ============================================================

def detect_bos(candles, lookback=10):

    if len(candles) < lookback + 3:
        return "NONE"

    previous = candles[
        -(lookback + 1):-1
    ]

    last = candles[-1]

    previous_high = max(
        c["high"] for c in previous
    )

    previous_low = min(
        c["low"] for c in previous
    )

    if last["close"] > previous_high:
        return "BULLISH BOS"

    if last["close"] < previous_low:
        return "BEARISH BOS"

    return "NONE"


# ============================================================
# WATCH ZONE
# ============================================================

def calculate_watch_zone(
    price,
    atr_value,
    sweep_type,
    swing_low,
    swing_high
):

    if atr_value is None or atr_value <= 0:
        atr_value = price * 0.005

    zone_size = atr_value * 0.25

    # If a sweep happened, zone is based around
    # the liquidity level rather than blindly around price.

    if (
        sweep_type == "BULLISH SWEEP"
        and swing_low is not None
    ):

        center = swing_low

    elif (
        sweep_type == "BEARISH SWEEP"
        and swing_high is not None
    ):

        center = swing_high

    else:

        center = price

    return (
        center - zone_size,
        center + zone_size
    )


# ============================================================
# RETEST
# ============================================================

def detect_retest(
    candles,
    bos_type,
    zone_low,
    zone_high
):

    if len(candles) < 2:
        return False

    last = candles[-1]

    touched = (
        last["low"] <= zone_high
        and last["high"] >= zone_low
    )

    if not touched:
        return False

    if bos_type == "BULLISH BOS":

        return last["close"] >= zone_low

    if bos_type == "BEARISH BOS":

        return last["close"] <= zone_high

    return False


# ============================================================
# ENTRY ENGINE V5.7
# ============================================================

def entry_engine(
    bias,
    sweep,
    candle,
    bos,
    retest
):

    bullish_sweep = (
        sweep == "BULLISH SWEEP"
    )

    bearish_sweep = (
        sweep == "BEARISH SWEEP"
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

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if bias == "BUY":

        if (
            bullish_sweep
            and bullish_candle
            and bullish_bos
            and retest
        ):

            return (
                "ENTRY READY",
                "BUY"
            )

        if bullish_sweep:
            return (
                "WAIT FOR CANDLE/BOS/RETEST",
                "BUY"
            )

        return (
            "WAIT FOR BULLISH SWEEP",
            "BUY"
        )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if bias == "SELL":

        if (
            bearish_sweep
            and bearish_candle
            and bearish_bos
            and retest
        ):

            return (
                "ENTRY READY",
                "SELL"
            )

        if bearish_sweep:
            return (
                "WAIT FOR CANDLE/BOS/RETEST",
                "SELL"
            )

        return (
            "WAIT FOR BEARISH SWEEP",
            "SELL"
        )

    return (
        "WAIT FOR BIAS",
        "WAIT"
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
            f"{len(candles_15m)} candles"
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

    sweep = liquidity_sweep(
        candles_15m,
        20
    )

    candle = candle_confirmation(
        candles_15m
    )

    bos = detect_bos(
        candles_15m,
        10
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

    # ========================================================
    # BIAS
    # ========================================================

    if (
        buy_score >= 55
        and buy_score > sell_score
    ):

        bias = "BUY"
        confidence = buy_score
        reasons = buy_reasons

    elif (
        sell_score >= 55
        and sell_score > buy_score
    ):

        bias = "SELL"
        confidence = sell_score
        reasons = sell_reasons

    else:

        # Keep directional bias when one side is clearly
        # stronger, but do not call it an entry signal.
        if buy_score > sell_score:
            bias = "BUY"
            confidence = buy_score
            reasons = buy_reasons

        elif sell_score > buy_score:
            bias = "SELL"
            confidence = sell_score
            reasons = sell_reasons

        else:
            bias = "WAIT"
            confidence = 0
            reasons = []

    # ========================================================
    # WATCH ZONE
    # ========================================================

    sweep_type = sweep["type"]

    zone_low, zone_high = calculate_watch_zone(
        price,
        atr_value,
        sweep_type,
        swing_low,
        swing_high
    )

    # ========================================================
    # RETEST
    # ========================================================

    retest = detect_retest(
        candles_15m,
        bos,
        zone_low,
        zone_high
    )

    # ========================================================
    # ENTRY ENGINE
    # ========================================================

    trigger, entry_direction = entry_engine(
        bias,
        sweep_type,
        candle,
        bos,
        retest
    )

    # ========================================================
    # FINAL SIGNAL
    # ========================================================

    if trigger == "ENTRY READY":

        direction = entry_direction

    else:

        direction = "WAIT"

    # ========================================================
    # SL / TP
    # ========================================================

    if atr_value is None or atr_value <= 0:
        atr_value = price * 0.005

    if direction == "BUY":

        entry_price = price

        sl = min(
            swing_low,
            entry_price - atr_value * 1.2
        )

        risk = (
            entry_price - sl
        )

        tp1 = entry_price + risk
        tp2 = entry_price + risk * 2

    elif direction == "SELL":

        entry_price = price

        sl = max(
            swing_high,
            entry_price + atr_value * 1.2
        )

        risk = (
            sl - entry_price
        )

        tp1 = entry_price - risk
        tp2 = entry_price - risk * 2

    else:

        entry_price = None
        sl = None
        tp1 = None
        tp2 = None

    return {
        "price": price,
        "bias": bias,
        "direction": direction,
        "confidence": confidence,

        "structure": structure,
        "h1_trend": h1_trend,

        "rsi": rsi_value,
        "adx": adx_value,
        "atr": atr_value,

        "liquidity": sweep_type,
        "liquidity_level": sweep["level"],

        "candle": candle,
        "bos": bos,
        "retest": retest,

        "trigger": trigger,

        "zone_low": zone_low,
        "zone_high": zone_high,

        "swing_low": swing_low,
        "swing_high": swing_high,

        "entry_price": entry_price,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,

        "reasons": reasons,

        "source_15m": source_15m,
        "source_1h": source_1h,
    }


# ============================================================
# FORMAT
# ============================================================

def format_signal(asset, result):

    if result is None:

        return (
            "❌ *DATA CANDLE GAGAL*\n\n"
            "15M candle tidak mencukupi.\n"
            "Fallback source sudah dicuba.\n\n"
            "🔄 Cuba semula beberapa saat lagi."
        )

    if asset == "gold":

        name = "GOLD (XAUUSD)"
        emoji = "🥇"

    else:

        name = "BTC"
        emoji = "₿"

    price = result["price"]

    direction = result["direction"]
    bias = result["bias"]

    confidence = result["confidence"]

    rsi_value = result["rsi"]
    adx_value = result["adx"]

    # ========================================================
    # HEADER
    # ========================================================

    message = (
        f"{emoji} *{name} SIGNAL V5.7*\n\n"
        f"💰 Harga: `${price:,.2f}`\n\n"
    )

    if direction == "BUY":

        message += (
            "🟢 *SIGNAL: BUY*\n"
            "🔥 ENTRY READY\n\n"
        )

    elif direction == "SELL":

        message += (
            "🔴 *SIGNAL: SELL*\n"
            "🔥 ENTRY READY\n\n"
        )

    else:

        message += (
            "🟡 *SIGNAL: WAIT*\n"
            "⏳ Tunggu confirmation\n\n"
        )

    # ========================================================
    # BIAS / METRICS
    # ========================================================

    message += (
        f"🧭 *Bias:* `{bias}`\n"
        f"💯 *Confidence:* `{confidence}%`\n"
        f"📐 *Structure:* `{result['structure']}`\n"
        f"🕐 *1H Trend:* `{result['h1_trend']}`\n"
        f"📊 *RSI:* `{rsi_value:.1f}`\n"
        f"📈 *ADX:* `{adx_value:.1f}`\n\n"
    )

    # ========================================================
    # LIQUIDITY
    # ========================================================

    message += (
        "💧 *LIQUIDITY*\n"
        f"`{result['liquidity']}`\n"
    )

    if result["liquidity_level"] is not None:

        message += (
            f"Level: "
            f"`{result['liquidity_level']:,.2f}`\n"
        )

    message += "\n"

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

    retest_text = (
        "CONFIRMED"
        if result["retest"]
        else "NONE"
    )

    message += (
        "🔄 *RETEST*\n"
        f"`{retest_text}`\n\n"
    )

    # ========================================================
    # ENTRY TRIGGER
    # ========================================================

    if result["trigger"] == "ENTRY READY":

        trigger_text = (
            "🟢 ENTRY READY"
        )

    else:

        trigger_text = (
            "🟡 "
            + result["trigger"]
        )

    message += (
        "⏳ *ENTRY TRIGGER*\n"
        f"`{trigger_text}`\n\n"
    )

    # ========================================================
    # WATCH ZONE
    # ========================================================

    message += (
        "🟡 *WATCH ZONE*\n"
        f"`{result['zone_low']:,.2f}"
        " – "
        f"{result['zone_high']:,.2f}`\n\n"

        "📉 *SWING LOW*\n"
        f"`{result['swing_low']:,.2f}`\n\n"

        "📈 *SWING HIGH*\n"
        f"`{result['swing_high']:,.2f}`\n\n"
    )

    # ========================================================
    # ENTRY / SL / TP
    # ========================================================

    if direction in ("BUY", "SELL"):

        message += (
            "🎯 *ENTRY*\n"
            f"`{result['entry_price']:,.2f}`\n\n"

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

    message += "🧠 *ANALYSIS*\n"

    for reason in result["reasons"]:

        message += (
            f"• {reason}\n"
        )

    if result["trigger"] != "ENTRY READY":

        if bias == "BUY":

            message += (
                "• Untuk BUY: tunggu bullish "
                "sweep → candle → BOS → retest\n"
            )

        elif bias == "SELL":

            message += (
                "• Untuk SELL: tunggu bearish "
                "sweep → candle → BOS → retest\n"
            )

        else:

            message += (
                "• Tunggu bias market menjadi lebih jelas\n"
            )

    # ========================================================
    # SOURCE
    # ========================================================

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
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🤖 *GOLD & BTC SIGNAL BOT V5.7*\n\n"

        "📌 *COMMANDS*\n\n"

        "/price\n"
        "➡️ Harga Gold & BTC\n\n"

        "/signal gold\n"
        "➡️ Gold V5.7\n\n"

        "/signal btc\n"
        "➡️ BTC V5.7\n\n"

        "/news\n"
        "➡️ News monitor\n\n"

        "🧠 Technical engine V5.7\n"
        "📊 15M + 1H\n"
        "💧 Liquidity Sweep\n"
        "🕯 Candle Confirmation\n"
        "📐 Break of Structure\n"
        "🔄 Retest Detection\n"
        "🎯 Entry Trigger\n"
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
        "📈 *HARGA SEMASA V5.7*\n\n"
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
        "🧠 *SIGNAL V5.7*\n\n"
        "📡 Mengambil candle...\n"
        "📊 15M + 1H\n"
        "💧 Memeriksa liquidity...\n"
        "🕯 Memeriksa candle...\n"
        "📐 Memeriksa BOS...\n"
        "🔄 Memeriksa retest...\n"
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
        "📰 *NEWS MONITOR V5.7*\n\n"

        "🥇 *GOLD*\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• CPI\n"
        "• NFP\n"
        "• Interest Rate\n\n"

        "₿ *BITCOIN*\n"
        "• ETF Flow\n"
        "• Funding Rate\n"
        "• BTC Dominance\n"
        "• US Macro Data\n\n"

        "⚠️ Live news engine belum diaktifkan."
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
    print("🤖 GOLD & BTC SIGNAL BOT V5.7")
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
        "🚀 Starting V5.7..."
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
            "🚀 V5.7 BOT AKTIF!"
        )

        print(
            "📡 Telegram polling aktif!"
        )

        print(
            "🥇 Gold: GC=F -> XAUUSD=X"
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
            "🎯 Entry Trigger"
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
