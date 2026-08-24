import os, logging, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Safari/537.36"
})

def gold_market_status():
    now = datetime.now(MY_TZ)
    wd = now.weekday()
    mins = now.hour * 60 + now.minute
    if wd == 5:
        return False, "WEEKEND"
    if wd == 6 and mins < 360:
        return False, "WEEKEND"
    if 300 <= mins < 360:
        return False, "DAILY BREAK"
    return True, "OPEN"

def btc_market_status():
    return True, "OPEN 24/7"

def binance_candles(symbol, interval="15m", limit=500):
    url = "https://api.binance.com/api/v3/klines"
    try:
        r = SESSION.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
        if r.status_code != 200:
            return []
        candles = []
        for item in r.json():
            try:
                candles.append({
                    "time": item[0],
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[7])
                })
            except (IndexError, TypeError, ValueError):
                continue
        if candles:
            logger.info("Binance %s: %d candles OK", symbol, len(candles))
        return candles
    except Exception as e:
        logger.warning("Binance %s error: %s", symbol, e)
        return []

def coingecko_candles(coin_id, days=30):
    url = "https://api.coingecko.com/api/v3/coins/" + coin_id + "/market_chart"
    try:
        r = SESSION.get(url, params={"vs_currency": "usd", "days": days, "interval": "daily"}, timeout=15)
        if r.status_code != 200:
            return []
        prices = r.json().get("prices", [])
        if not prices:
            return []
        candles = []
        for i in range(len(prices) - 1):
            try:
                candles.append({
                    "time": prices[i][0],
                    "open": float(prices[i][1]),
                    "high": float(prices[i][1]),
                    "low": float(prices[i+1][1]),
                    "close": float(prices[i+1][1]),
                    "volume": 0
                })
            except (IndexError, TypeError, ValueError):
                continue
        if candles:
            logger.info("CoinGecko %s: %d candles OK", coin_id, len(candles))
        return candles
    except Exception as e:
        logger.warning("CoinGecko %s error: %s", coin_id, e)
        return []

def metals_live_candles():
    try:
        r = SESSION.get("https://api.metals.live/v1/spot/gold", timeout=10)
        if r.status_code == 200:
            price = r.json().get("price", 0)
            if price > 0:
                return [{"time": int(datetime.now().timestamp() * 1000),
                         "open": price, "high": price, "low": price,
                         "close": price, "volume": 0}]
        return []
    except Exception as e:
        logger.warning("Metals.live error: %s", e)
        return []

def get_candles(asset, minimum=60):
    if asset == "btc":
        sources = [
            ("Binance 15m", lambda: binance_candles("BTCUSDT", "15m", 500)),
            ("Binance 1h", lambda: binance_candles("BTCUSDT", "1h", 500)),
            ("CoinGecko", lambda: coingecko_candles("bitcoin", 30)),
        ]
    else:
        sources = [
            ("Metals.live", lambda: metals_live_candles()),
            ("CoinGecko Gold", lambda: coingecko_candles("bitcoin", 30)),
        ]
    for source_name, source_func in sources:
        try:
            candles = source_func()
            if len(candles) >= minimum:
                logger.info("%s from %s: %d candles OK", asset, source_name, len(candles))
                return candles, source_name
            logger.warning("%s from %s: only %d candles", asset, source_name, len(candles))
        except Exception as e:
            logger.warning("%s from %s failed: %s", asset, source_name, e)
            continue
    return [], None

def get_live_price(asset):
    if asset == "btc":
        apis = [
            ("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
             lambda r: r.json().get("bitcoin", {}).get("usd")),
            ("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
             lambda r: float(r.json().get("price", 0))),
        ]
    else:
        apis = [
            ("https://api.metals.live/v1/spot/gold",
             lambda r: r.json().get("price")),
            ("https://api.gold-api.com/price/XAU",
             lambda r: r.json().get("price")),
        ]
    for url, parser in apis:
        try:
            r = SESSION.get(url, timeout=10)
            if r.status_code == 200:
                price = parser(r)
                if price and float(price) > 0:
                    source = url.split("/")[2]
                    return float(price), source
        except Exception as e:
            logger.warning("API %s error: %s", url, e)
            continue
    return None, None

def ema(v, n):
    if len(v) < n:
        return None
    k = 2 / (n + 1)
    x = sum(v[:n]) / n
    for p in v[n:]:
        x = (p - x) * k + x
    return x

def rsi(v, n=14):
    if len(v) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(v)):
        d = v[i] - v[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag, al = sum(gains[:n])/n, sum(losses[:n])/n
    for i in range(n, len(gains)):
        ag = ((ag*(n-1))+gains[i])/n
        al = ((al*(n-1))+losses[i])/n
    if al == 0:
        return 100.0
    return 100 - 100/(1 + ag/al)

def atr(c, n=14):
    if len(c) < n + 1:
        return None
    tr = []
    for i in range(1, len(c)):
        x, p = c[i], c[i-1]
        tr.append(max(x["high"]-x["low"], abs(x["high"]-p["close"]), abs(x["low"]-p["close"])))
    if len(tr) < n:
        return None
    a = sum(tr[:n])/n
    for x in tr[n:]:
        a = ((a*(n-1))+x)/n
    return a

def adx(c, n=14):
    if len(c) < n*2+1:
        return None
    tr, pdm, mdm = [], [], []
    for i in range(1, len(c)):
        x, p = c[i], c[i-1]
        hd, ld = x["high"]-p["high"], p["low"]-x["low"]
        tr.append(max(x["high"]-x["low"], abs(x["high"]-p["close"]), abs(x["low"]-p["close"])))
        pdm.append(hd if hd > ld and hd > 0 else 0)
        mdm.append(ld if ld > hd and ld > 0 else 0)
    ta, pa, ma = sum(tr[:n])/n, sum(pdm[:n])/n, sum(mdm[:n])/n
    dx = []
    for i in range(n, len(tr)):
        ta = ((ta*(n-1))+tr[i])/n
        pa = ((pa*(n-1))+pdm[i])/n
        ma = ((ma*(n-1))+mdm[i])/n
        if ta == 0:
            continue
        pdi, mdi = 100*pa/ta, 100*ma/ta
        if pdi+mdi == 0:
            continue
        dx.append(100*abs(pdi-mdi)/(pdi+mdi))
    return sum(dx[-n:])/n if len(dx) >= n else None

def get_swings(c, n=30):
    if not c:
        return None, None
    x = c[-min(n, len(c)):]
    return min(z["low"] for z in x), max(z["high"] for z in x)

def market_structure(c):
    if len(c) < 20:
        return "NEUTRAL"
    a, b = c[-20:-10], c[-10:]
    ah, bh = max(x["high"] for x in a), max(x["high"] for x in b)
    al, bl = min(x["low"] for x in a), min(x["low"] for x in b)
    if bh > ah and bl > al:
        return "BULLISH"
    if bh < ah and bl < al:
        return "BEARISH"
    return "NEUTRAL"

def candle_confirmation(c):
    if len(c) < 3:
        return "NONE"
    p, x = c[-2], c[-1]
    pb = p["close"] < p["open"]
    pa = p["close"] > p["open"]
    xb = x["close"] > x["open"]
    xa = x["close"] < x["open"]
    if pb and xb and x["open"] <= p["close"] and x["close"] >= p["open"]:
        return "BULLISH ENGULFING"
    if pa and xa and x["open"] >= p["close"] and x["close"] <= p["open"]:
        return "BEARISH ENGULFING"
    rng = x["high"] - x["low"]
    body = abs(x["close"] - x["open"])
    if rng > 0 and body/rng >= 0.65:
        return "BULLISH CANDLE" if xb else "BEARISH CANDLE"
    return "NONE"

def liquidity_sweep(c):
    if len(c) < 12:
        return "NONE", None
    x = c[-1]
    prev = c[-6:-1]
    hi = max(z["high"] for z in prev)
    lo = min(z["low"] for z in prev)
    if x["low"] < lo and x["close"] > lo:
        return "BULLISH SWEEP", lo
    if x["high"] > hi and x["close"] < hi:
        return "BEARISH SWEEP", hi
    return "NONE", None

def detect_bos(c):
    if len(c) < 15:
        return "NONE", None
    x = c[-1]
    p = c[-11:-1]
    hi = max(z["high"] for z in p)
    lo = min(z["low"] for z in p)
    if x["close"] > hi:
        return "BULLISH BOS", hi
    if x["close"] < lo:
        return "BEARISH BOS", lo
    return "NONE", None

def detect_retest(c, bos, bp, av):
    if bos == "NONE" or bp is None or av is None:
        return "NONE", None
    x = c[-1]
    tol = av * 0.20
    if bos == "BULLISH BOS" and x["low"] <= bp+tol and x["close"] > bp:
        return "BULLISH RETEST", bp
    if bos == "BEARISH BOS" and x["high"] >= bp-tol and x["close"] < bp:
        return "BEARISH RETEST", bp
    return "NONE", None

def calculate_bias(e20, e50, structure, h1, rv):
    buy = sell = 0
    if e20 is not None and e50 is not None:
        if e20 > e50:
            buy += 1
        elif e20 < e50:
            sell += 1
    if structure == "BULLISH":
        buy += 2
    elif structure == "BEARISH":
        sell += 2
    if h1 == "BULLISH":
        buy += 2
    elif h1 == "BEARISH":
        sell += 2
    if rv is not None:
        if 50 <= rv < 70:
            buy += 1
        elif 30 < rv < 50:
            sell += 1
    if buy >= sell+2:
        return "BUY", buy, sell
    if sell >= buy+2:
        return "SELL", buy, sell
    return "NEUTRAL", buy, sell

def build_zone(price, av, ref=None):
    av = av if av and av > 0 else price * 0.005
    ref = ref if ref is not None else price
    z = av * 0.20
    return ref-z, ref+z

def analyze_asset(asset):
    if asset == "gold":
        opened, reason = gold_market_status()
    else:
        opened, reason = btc_market_status()
    if not opened:
        return {"market_open": False, "market_reason": reason, "asset": asset}

    c15, s15 = get_candles(asset, 60)
    c1h, s1h = get_candles(asset, 50)

    if len(c15) < 60:
        return None

    closes = [x["close"] for x in c15]
    price = closes[-1]
    e20, e50 = ema(closes, 20), ema(closes, 50)
    rv = rsi(closes)
    av = atr(c15)
    ax = adx(c15)
    structure = market_structure(c15)
    slw, shw = get_swings(c15, 30)

    h1trend = "NEUTRAL"
    if len(c1h) >= 50:
        hc = [x["close"] for x in c1h]
        a, b = ema(hc, 20), ema(hc, 50)
        if a is not None and b is not None:
            if a > b:
                h1trend = "BULLISH"
            elif a < b:
                h1trend = "BEARISH"

    bias, bp, sp = calculate_bias(e20, e50, structure, h1trend, rv)
    liq, lprice = liquidity_sweep(c15)
    candle = candle_confirmation(c15)
    bos, bosprice = detect_bos(c15)
    retest, retprice = detect_retest(c15, bos, bosprice, av)

    score = 0
    if bias == "BUY":
        if liq == "BULLISH SWEEP":
            score += 25
        if candle in ("BULLISH ENGULFING", "BULLISH CANDLE"):
            score += 20
        if bos == "BULLISH BOS":
            score += 25
        if retest == "BULLISH RETEST":
            score += 30
    elif bias == "SELL":
        if liq == "BEARISH SWEEP":
            score += 25
        if candle in ("BEARISH ENGULFING", "BEARISH CANDLE"):
            score += 20
        if bos == "BEARISH BOS":
            score += 25
        if retest == "BEARISH RETEST":
            score += 30

    direction = "WAIT"
    if bias == "BUY" and score >= 70 and liq == "BULLISH SWEEP" and candle in ("BULLISH ENGULFING", "BULLISH CANDLE") and bos == "BULLISH BOS":
        direction = "BUY"
    elif bias == "SELL" and score >= 70 and liq == "BEARISH SWEEP" and candle in ("BEARISH ENGULFING", "BEARISH CANDLE") and bos == "BEARISH BOS":
        direction = "SELL"

    if direction in ("BUY", "SELL"):
        confidence = min(95, int(55 + score * 0.40))
    else:
        confidence = min(59, int(40 + abs(bp-sp)*4 + score * 0.10))

    ref = bosprice if bosprice is not None else lprice
    zl, zh = build_zone(price, av, ref)

    sl = tp1 = tp2 = None
    if direction == "BUY":
        protect = lprice if lprice is not None else slw
        sl = protect - av * 0.30
        risk = max(price - sl, av)
        tp1 = price + risk * 1.5
        tp2 = price + risk * 2.5
    elif direction == "SELL":
        protect = lprice if lprice is not None else shw
        sl = protect + av * 0.30
        risk = max(sl - price, av)
        tp1 = price - risk * 1.5
        tp2 = price - risk * 2.5

    missing = []
    if bias == "BUY":
        if liq != "BULLISH SWEEP":
            missing.append("Bullish liquidity sweep")
        if candle not in ("BULLISH ENGULFING", "BULLISH CANDLE"):
            missing.append("Bullish candle confirmation")
        if bos != "BULLISH BOS":
            missing.append("Bullish BOS")
        if retest != "BULLISH RETEST":
            missing.append("Retest")
    elif bias == "SELL":
        if liq != "BEARISH SWEEP":
            missing.append("Bearish liquidity sweep")
        if candle not in ("BEARISH ENGULFING", "BEARISH CANDLE"):
            missing.append("Bearish candle confirmation")
        if bos != "BEARISH BOS":
            missing.append("Bearish BOS")
        if retest != "BEARISH RETEST":
            missing.append("Retest")
    else:
        missing.append("Directional bias")

    reasons = []
    if e20 and e50:
        reasons.append("EMA20 di atas EMA50" if e20 > e50 else "EMA20 di bawah EMA50")
    if structure != "NEUTRAL":
        reasons.append("Market structure " + structure)
    if h1trend != "NEUTRAL":
        reasons.append("Trend 1H " + h1trend)
    if liq != "NONE":
        reasons.append(liq)
    if candle != "NONE":
        reasons.append(candle)
    if bos != "NONE":
        reasons.append(bos)
    if retest != "NONE":
        reasons.append(retest)
    if not reasons:
        reasons.append("Belum ada confirmation")

    return {
        "market_open": True, "price": price, "direction": direction, "bias": bias,
        "confidence": confidence, "trigger_score": score, "structure": structure,
        "h1_trend": h1trend, "rsi": rv, "adx": ax, "atr": av, "liquidity": liq,
        "liquidity_price": lprice, "candle_confirmation": candle, "bos": bos,
        "bos_price": bosprice, "retest": retest, "retest_price": retprice,
        "entry_low": zl, "entry_high": zh, "swing_low": slw, "swing_high": shw,
        "sl": sl, "tp1": tp1, "tp2": tp2, "reasons": reasons, "missing": missing,
        "source_15m": s15 or "N/A", "source_1h": s1h or "N/A"
    }

def format_closed(asset, result):
    now = datetime.now(MY_TZ)
    name = "GOLD XAUUSD" if asset == "gold" else "BITCOIN BTC"
    return "🔴 *" + name + " MARKET CLOSED*\n\n🕐 `" + now.strftime("%d/%m/%Y %H:%M") + "`\n📌 Status: `" + result.get("market_reason", "CLOSED") + "`"

def format_signal(asset, r):
    if r is None:
        return "❌ *DATA CANDLE GAGAL*\n\n60 candles tidak tersedia.\n🔄 Cuba semula selepas beberapa saat."
    if not r.get("market_open", True):
        return format_closed(asset, r)

    name = "GOLD (XAUUSD)" if asset == "gold" else "BITCOIN (BTC)"
    emoji = "🥇" if asset == "gold" else "₿"
    d = r["direction"]
    b = r["bias"]

    msg = emoji + " *" + name + " SIGNAL V7.5*\n\n"
    msg += "💰 Harga: `$" + "{:,.2f}".format(r["price"]) + "`\n"

    if d == "BUY":
        msg += "\n🟢 *SIGNAL: BUY*\n🚀 Entry trigger aktif\n"
    elif d == "SELL":
        msg += "\n🔴 *SIGNAL: SELL*\n🚀 Entry trigger aktif\n"
    else:
        msg += "\n🟡 *SIGNAL: WAIT*\n⏳ Tunggu confirmation\n"

    rsi_val = r["rsi"]
    adx_val = r["adx"]
    rsi_str = "{:.1f}".format(rsi_val) if rsi_val is not None else "N/A"
    adx_str = "{:.1f}".format(adx_val) if adx_val is not None else "N/A"

    msg += "\n🧭 *Bias:* `" + b + "`\n"
    msg += "💯 *Confidence:* `" + str(r["confidence"]) + "%`\n"
    msg += "🎯 *Trigger Score:* `" + str(r["trigger_score"]) + "/100`\n"
    msg += "📐 *Structure:* `" + r["structure"] + "`\n"
    msg += "🕐 *1H Trend:* `" + r["h1_trend"] + "`\n"
    msg += "📊 *RSI:* `" + rsi_str + "`\n"
    msg += "📈 *ADX:* `" + adx_str + "`\n\n"

    msg += "💧 *LIQUIDITY*\n`" + r["liquidity"] + "`\n\n"
    msg += "🕯 *CANDLE CONFIRMATION*\n`" + r["candle_confirmation"] + "`\n\n"
    msg += "📐 *BREAK OF STRUCTURE*\n`" + r["bos"] + "`\n\n"
    msg += "🔄 *RETEST*\n`" + r["retest"] + "`\n\n"

    if d == "BUY":
        trig = "🟢 BUY TRIGGER ACTIVE"
    elif d == "SELL":
        trig = "🔴 SELL TRIGGER ACTIVE"
    elif b == "BUY":
        if r["liquidity"] != "BULLISH SWEEP":
            trig = "🟡 WAIT FOR BULLISH SWEEP"
        elif r["candle_confirmation"] not in ("BULLISH ENGULFING", "BULLISH CANDLE"):
            trig = "🟡 WAIT FOR BULLISH CANDLE"
        elif r["bos"] != "BULLISH BOS":
            trig = "🟡 WAIT FOR BULLISH BOS"
        else:
            trig = "🟡 WAIT FOR BULLISH RETEST"
    elif b == "SELL":
        if r["liquidity"] != "BEARISH SWEEP":
            trig = "🟡 WAIT FOR BEARISH SWEEP"
        elif r["candle_confirmation"] not in ("BEARISH ENGULFING", "BEARISH CANDLE"):
            trig = "🟡 WAIT FOR BEARISH CANDLE"
        elif r["bos"] != "BEARISH BOS":
            trig = "🟡 WAIT FOR BEARISH BOS"
        else:
            trig = "🟡 WAIT FOR BEARISH RETEST"
    else:
        trig = "🟡 WAIT FOR DIRECTION"

    msg += "⏳ *ENTRY TRIGGER*\n" + trig + "\n\n"
    msg += "🟡 *ENTRY / WATCH ZONE*\n`" + "{:,.2f}".format(r["entry_low"]) + " - " + "{:,.2f}".format(r["entry_high"]) + "`\n\n"
    msg += "📉 *SWING LOW*\n`" + "{:,.2f}".format(r["swing_low"]) + "`\n\n"
    msg += "📈 *SWING HIGH*\n`" + "{:,.2f}".format(r["swing_high"]) + "`\n\n"

    if d in ("BUY", "SELL"):
        msg += "🛑 *STOP LOSS*\n`" + "{:,.2f}".format(r["sl"]) + "`\n\n"
        msg += "🎯 *TP1*\n`" + "{:,.2f}".format(r["tp1"]) + "`\n\n"
        msg += "🎯 *TP2*\n`" + "{:,.2f}".format(r["tp2"]) + "`\n\n"

    msg += "🧠 *ANALYSIS*\n"
    for x in r["reasons"]:
        msg += "• " + x + "\n"

    if d == "WAIT":
        msg += "\n⏳ *BELUM LENGKAP*\n"
        for x in r["missing"]:
            msg += "• Tunggu " + x + "\n"

    msg += "\n📡 *DATA SOURCE*\n"
    msg += "15M: `" + r["source_15m"] + "`\n"
    msg += "1H: `" + r["source_1h"] + "`\n\n"
    msg += "🚫 Tiada auto-trading.\n"
    msg += "⚠️ Technical signal sahaja. Bukan jaminan profit."
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *GOLD & BTC SIGNAL BOT V7.5*\n\n"
        "/price - Harga Gold & BTC\n"
        "/signal gold - Signal Gold\n"
        "/signal btc - Signal Bitcoin\n"
        "/news - News monitor\n\n"
        "📊 15M + 1H | EMA RSI ADX ATR\n"
        "💧 Liquidity | 🕯 Candle | 📐 BOS | 🔄 Retest\n"
        "🎯 Entry Zone / SL / TP\n"
        "🔄 Binance + CoinGecko + Metals.live\n"
        "🚫 Tiada auto-trading",
        parse_mode="Markdown"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📈 *HARGA SEMASA V7.5*\n\n"
    op, reason = gold_market_status()
    if not op:
        text += "🥇 *Gold XAUUSD*\n🔴 MARKET CLOSED\nStatus: `" + reason + "`\n\n"
    else:
        p, s = get_live_price("gold")
        if p:
            text += "🥇 *Gold XAUUSD*\n`$" + "{:,.2f}".format(p) + "`\nSource: `" + str(s) + "`\n\n"
        else:
            text += "🥇 *Gold XAUUSD*\n❌ Harga tidak tersedia\n\n"
    p, s = get_live_price("btc")
    if p:
        text += "₿ *Bitcoin BTC*\n`$" + "{:,.2f}".format(p) + "`\nSource: `" + str(s) + "`"
    else:
        text += "₿ *Bitcoin BTC*\n❌ Harga tidak tersedia"
    await update.message.reply_text(text, parse_mode="Markdown")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Pilih asset:\n/signal gold\n/signal btc")
        return
    asset = context.args[0].lower()
    if asset not in ("gold", "btc"):
        await update.message.reply_text("❌ Asset tidak disokong.\n/signal gold\n/signal btc")
        return
    status = await update.message.reply_text(
        "🧠 *SIGNAL V7.5*\n\n📡 Mengambil data...\n🔄 Multi-source fallback aktif...\n⏳ Sila tunggu...",
        parse_mode="Markdown"
    )
    try:
        result = analyze_asset(asset)
        msg = format_signal(asset, result)
        await status.edit_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Signal error")
        await status.edit_text("❌ *SIGNAL ERROR*\n\n`" + str(e) + "`", parse_mode="Markdown")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📰 *NEWS MONITOR V7.5*\n\n"
        "🥇 GOLD: USD Index, Federal Reserve, CPI, NFP\n\n"
        "₿ BTC: ETF Flow, Funding Rate, BTC Dominance\n\n"
        "⚠️ News engine belum live.",
        parse_mode="Markdown"
    )

async def error_handler(update, context):
    logger.error("Telegram error:", exc_info=context.error)

def main():
    print("BOT V7.5 STARTING")
    if not TOKEN:
        print("BOT_TOKEN NOT FOUND")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("news", news))
    app.add_error_handler(error_handler)
    print("BOT V7.5 RUNNING")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
