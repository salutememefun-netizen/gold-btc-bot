import os, logging, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# GOLD & BTC SIGNAL BOT V7.2
# DATA RELIABILITY + 15M FALLBACK
# ============================================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

SYMBOLS = {
    "gold": ["GC=F", "XAUUSD=X"],
    "btc": ["BTC-USD"],
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Safari/537.36"
})

# ---------------- MARKET STATUS ----------------

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

# ---------------- YAHOO DATA ----------------

def yahoo_candles(symbol, interval="15m", range_value="5d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        r = SESSION.get(url, params={
            "interval": interval,
            "range": range_value,
            "includePrePost": "true",
            "events": "div,splits",
        }, timeout=20)
        if r.status_code != 200:
            logger.warning("%s HTTP %s", symbol, r.status_code)
            return []
        result = r.json().get("chart", {}).get("result")
        if not result:
            return []
        x = result[0]
        ts = x.get("timestamp") or []
        ql = x.get("indicators", {}).get("quote", [])
        if not ql:
            return []
        q = ql[0]
        o, h, l, c = q.get("open", []), q.get("high", []), q.get("low", []), q.get("close", [])
        out = []
        for i, t in enumerate(ts):
            try:
                vals = (o[i], h[i], l[i], c[i])
                if any(v is None for v in vals):
                    continue
                out.append({"time": t, "open": float(o[i]), "high": float(h[i]),
                            "low": float(l[i]), "close": float(c[i])})
            except (IndexError, TypeError, ValueError):
                continue
        return out
    except Exception as e:
        logger.warning("Yahoo %s error: %s", symbol, e)
        return []

def get_candles(asset, interval, ranges=None, minimum=20):
    if ranges is None:
        ranges = ["5d", "1mo", "3mo"]
    for symbol in SYMBOLS.get(asset, []):
        for rv in ranges:
            candles = yahoo_candles(symbol, interval, rv)
            if len(candles) >= minimum:
                logger.info("%s %s = %d candles [%s/%s]", asset, interval, len(candles), symbol, rv)
                return candles, symbol
            logger.warning("%s %s insufficient: %d [%s/%s]", asset, interval, len(candles), symbol, rv)
    return [], None

def get_live_price(asset):
    for symbol in SYMBOLS.get(asset, []):
        try:
            r = SESSION.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                timeout=15
            )
            if r.status_code != 200:
                continue
            result = r.json().get("chart", {}).get("result")
            if not result:
                continue
            x = result[0]
            p = x.get("meta", {}).get("regularMarketPrice")
            if p is None:
                q = x.get("indicators", {}).get("quote", [])
                closes = q[0].get("close", []) if q else []
                for v in reversed(closes):
                    if v is not None:
                        p = v
                        break
            if p is not None:
                return float(p), symbol
        except Exception as e:
            logger.warning("Price %s error: %s", symbol, e)
    return None, None

# ---------------- INDICATORS ----------------

def ema(v, n):
    if len(v) < n: return None
    k = 2 / (n + 1)
    x = sum(v[:n]) / n
    for p in v[n:]:
        x = (p - x) * k + x
    return x

def rsi(v, n=14):
    if len(v) < n + 1: return None
    gains, losses = [], []
    for i in range(1, len(v)):
        d = v[i] - v[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag, al = sum(gains[:n])/n, sum(losses[:n])/n
    for i in range(n, len(gains)):
        ag = ((ag*(n-1))+gains[i])/n
        al = ((al*(n-1))+losses[i])/n
    if al == 0: return 100.0
    return 100 - 100/(1 + ag/al)

def atr(c, n=14):
    if len(c) < n + 1: return None
    tr = []
    for i in range(1, len(c)):
        x, p = c[i], c[i-1]
        tr.append(max(x["high"]-x["low"], abs(x["high"]-p["close"]), abs(x["low"]-p["close"])))
    if len(tr) < n: return None
    a = sum(tr[:n])/n
    for x in tr[n:]:
        a = ((a*(n-1))+x)/n
    return a

def adx(c, n=14):
    if len(c) < n*2+1: return None
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
        if ta == 0: continue
        pdi, mdi = 100*pa/ta, 100*ma/ta
        if pdi+mdi == 0: continue
        dx.append(100*abs(pdi-mdi)/(pdi+mdi))
    return sum(dx[-n:])/n if len(dx) >= n else None

# ---------------- STRUCTURE ----------------

def get_swings(c, n=30):
    if not c: return None, None
    x = c[-min(n, len(c)):]
    return min(z["low"] for z in x), max(z["high"] for z in x)

def market_structure(c):
    if len(c) < 20: return "NEUTRAL"
    a, b = c[-20:-10], c[-10:]
    ah, bh = max(x["high"] for x in a), max(x["high"] for x in b)
    al, bl = min(x["low"] for x in a), min(x["low"] for x in b)
    if bh > ah and bl > al: return "BULLISH"
    if bh < ah and bl < al: return "BEARISH"
    return "NEUTRAL"

def candle_confirmation(c):
    if len(c) < 3: return "NONE"
    p, x = c[-2], c[-1]
    pb, pa = p["close"] < p["open"], p["close"] > p["open"]
    xb, xa = x["close"] > x["open"], x["close"] < x["open"]
    if pb and xb and x["open"] <= p["close"] and x["close"] >= p["open"]:
        return "BULLISH ENGULFING"
    if pa and xa and x["open"] >= p["close"] and x["close"] <= p["open"]:
        return "BEARISH ENGULFING"
    rng, body = x["high"]-x["low"], abs(x["close"]-x["open"])
    if rng > 0 and body/rng >= .65:
        return "BULLISH CANDLE" if xb else "BEARISH CANDLE"
    return "NONE"

def liquidity_sweep(c):
    if len(c) < 12: return "NONE", None
    x = c[-1]
    prev = c[-6:-1]
    hi, lo = max(z["high"] for z in prev), min(z["low"] for z in prev)
    if x["low"] < lo and x["close"] > lo: return "BULLISH SWEEP", lo
    if x["high"] > hi and x["close"] < hi: return "BEARISH SWEEP", hi
    return "NONE", None

def detect_bos(c):
    if len(c) < 15: return "NONE", None
    x = c[-1]
    p = c[-11:-1]
    hi, lo = max(z["high"] for z in p), min(z["low"] for z in p)
    if x["close"] > hi: return "BULLISH BOS", hi
    if x["close"] < lo: return "BEARISH BOS", lo
    return "NONE", None

def detect_retest(c, bos, bp, av):
    if bos == "NONE" or bp is None or av is None: return "NONE", None
    x, tol = c[-1], av*.20
    if bos == "BULLISH BOS" and x["low"] <= bp+tol and x["close"] > bp:
        return "BULLISH RETEST", bp
    if bos == "BEARISH BOS" and x["high"] >= bp-tol and x["close"] < bp:
        return "BEARISH RETEST", bp
    return "NONE", None

def calculate_bias(e20, e50, structure, h1, rv):
    buy = sell = 0
    if e20 is not None and e50 is not None:
        if e20 > e50: buy += 1
        elif e20 < e50: sell += 1
    if structure == "BULLISH": buy += 2
    elif structure == "BEARISH": sell += 2
    if h1 == "BULLISH": buy += 2
    elif h1 == "BEARISH": sell += 2
    if rv is not None:
        if 50 <= rv < 70: buy += 1
        elif 30 < rv < 50: sell += 1
    if buy >= sell+2: return "BUY", buy, sell
    if sell >= buy+2: return "SELL", buy, sell
    return "NEUTRAL", buy, sell

def build_zone(price, av, ref=None):
    av = av if av and av > 0 else price*.005
    ref = ref if ref is not None else price
    z = av*.20
    return ref-z, ref+z

# ---------------- ANALYSIS ----------------

def analyze_asset(asset):
    if asset == "gold":
        opened, reason = gold_market_status()
    else:
        opened, reason = btc_market_status()
    if not opened:
        return {"market_open": False, "market_reason": reason, "asset": asset}

    # V7.2: progressively wider fallback ranges
    c15, s15 = get_candles(asset, "15m", ["5d", "1mo", "3mo"], 60)
    c1h, s1h = get_candles(asset, "1h", ["1mo", "3mo", "6mo"], 50)

    # If 15M still unavailable, retry once with alternate symbol/source
    if len(c15) < 60:
        for sym in SYMBOLS.get(asset, []):
            c = yahoo_candles(sym, "15m", "1mo")
            if len(c) >= 60:
                c15, s15 = c, sym
                break

    if len(c15) < 60:
        return None

    closes = [x["close"] for x in c15]
    price = closes[-1]
    e20, e50 = ema(closes,20), ema(closes,50)
    rv, av, ax = rsi(closes), atr(c15), adx(c15)
    structure = market_structure(c15)
    slw, shw = get_swings(c15,30)

    h1trend = "NEUTRAL"
    if len(c1h) >= 50:
        hc = [x["close"] for x in c1h]
        a,b = ema(hc,20), ema(hc,50)
        if a is not None and b is not None:
            h1trend = "BULLISH" if a>b else "BEARISH" if a<b else "NEUTRAL"

    bias, bp, sp = calculate_bias(e20,e50,structure,h1trend,rv)
    liq, lprice = liquidity_sweep(c15)
    candle = candle_confirmation(c15)
    bos, bosprice = detect_bos(c15)
    retest, retprice = detect_retest(c15,bos,bosprice,av)

    score = 0
    if bias == "BUY":
        if liq == "BULLISH SWEEP": score += 25
        if candle in ("BULLISH ENGULFING","BULLISH CANDLE"): score += 20
        if bos == "BULLISH BOS": score += 25
        if retest == "BULLISH RETEST": score += 30
    elif bias == "SELL":
        if liq == "BEARISH SWEEP": score += 25
        if candle in ("BEARISH ENGULFING","BEARISH CANDLE"): score += 20
        if bos == "BEARISH BOS": score += 25
        if retest == "BEARISH RETEST": score += 30

    direction = "WAIT"
    if bias == "BUY" and score >= 70 and liq=="BULLISH SWEEP" and candle in ("BULLISH ENGULFING","BULLISH CANDLE") and bos=="BULLISH BOS":
        direction = "BUY"
    elif bias == "SELL" and score >= 70 and liq=="BEARISH SWEEP" and candle in ("BEARISH ENGULFING","BEARISH CANDLE") and bos=="BEARISH BOS":
        direction = "SELL"

    if direction in ("BUY","SELL"):
        confidence = min(95, int(55 + score*.40))
    else:
        confidence = min(59, int(40 + abs(bp-sp)*4 + score*.10))

    ref = bosprice if bosprice is not None else lprice
    zl, zh = build_zone(price,av,ref)

    sl = tp1 = tp2 = None
    if direction == "BUY":
        protect = lprice if lprice is not None else slw
        sl = protect - av*.30
        risk = max(price-sl,av)
        tp1, tp2 = price+risk*1.5, price+risk*2.5
    elif direction == "SELL":
        protect = lprice if lprice is not None else shw
        sl = protect + av*.30
        risk = max(sl-price,av)
        tp1, tp2 = price-risk*1.5, price-risk*2.5

    missing = []
    if bias == "BUY":
        if liq!="BULLISH SWEEP": missing.append("Bullish liquidity sweep")
        if candle not in ("BULLISH ENGULFING","BULLISH CANDLE"): missing.append("Bullish candle confirmation")
        if bos!="BULLISH BOS": missing.append("Bullish BOS")
        if retest!="BULLISH RETEST": missing.append("Retest")
    elif bias == "SELL":
        if liq!="BEARISH SWEEP": missing.append("Bearish liquidity sweep")
        if candle not in ("BEARISH ENGULFING","BEARISH CANDLE"): missing.append("Bearish candle confirmation")
        if bos!="BEARISH BOS": missing.append("Bearish BOS")
        if retest!="BEARISH RETEST": missing.append("Retest")
    else:
        missing.append("Directional bias")

    reasons = []
    if e20 and e50: reasons.append("EMA20 di atas EMA50" if e20>e50 else "EMA20 di bawah EMA50")
    if structure!="NEUTRAL": reasons.append(f"Market structure {structure}")
    if h1trend!="NEUTRAL": reasons.append(f"Trend 1H {h1trend}")
    if liq!="NONE": reasons.append(liq)
    if candle!="NONE": reasons.append(candle)
    if bos!="NONE": reasons.append(bos)
    if retest!="NONE": reasons.append(retest)
    if not reasons: reasons.append("Belum ada confirmation")

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

# ---------------- FORMAT ----------------

def format_closed(asset, result):
    now = datetime.now(MY_TZ)
    name = "GOLD XAUUSD" if asset=="gold" else "BITCOIN BTC"
    return f"🔴 *{name} MARKET CLOSED*\n\n🕐 `{now:%d/%m/%Y %H:%M}`\n📌 Status: `{result.get('market_reason','CLOSED')}`"

def format_signal(asset, r):
    if r is None:
        return "❌ *DATA CANDLE GAGAL*\n\n15M candle tidak mencukupi selepas semua fallback dicuba.\n🔄 Cuba semula beberapa saat lagi."
    if not r.get("market_open",True): return format_closed(asset,r)

    name, emoji = ("GOLD (XAUUSD)","🥇") if asset=="gold" else ("BITCOIN (BTC)","₿")
    d, b = r["direction"], r["bias"]
    msg = f"{emoji} *{name} SIGNAL V7.2*\n\n💰 Harga: `${r['price']:,.2f}`\n"
    msg += "\n🟢 *SIGNAL: BUY*\n🚀 Entry trigger aktif\n" if d=="BUY" else \
           "\n🔴 *SIGNAL: SELL*\n🚀 Entry trigger aktif\n" if d=="SELL" else \
           "\n🟡 *SIGNAL: WAIT*\n⏳ Tunggu confirmation\n"
    msg += f"\n🧭 *Bias:* `{b}`\n💯 *Confidence:* `{r['confidence']}%`\n🎯 *Trigger Score:* `{r['trigger_score']}/100`\n📐 *Structure:* `{r['structure']}`\n🕐 *1H Trend:* `{r['h1_trend']}`\n📊 *RSI:* `{r['rsi']:.1f}`\n📈 *ADX:* `{r['adx']:.1f}`\n\n"
    msg += f"💧 *LIQUIDITY*\n`{r['liquidity']}`\n\n🕯 *CANDLE CONFIRMATION*\n`{r['candle_confirmation']}`\n\n📐 *BREAK OF STRUCTURE*\n`{r['bos']}`\n\n🔄 *RETEST*\n`{r['retest']}`\n\n"

    if d=="BUY": trig="🟢 BUY TRIGGER ACTIVE"
    elif d=="SELL": trig="🔴 SELL TRIGGER ACTIVE"
    elif b=="BUY": trig="🟡 WAIT FOR " + ("BULLISH SWEEP" if r["liquidity"]!="BULLISH SWEEP" else "BULLISH CANDLE" if r["candle_confirmation"] not in ("BULLISH ENGULFING","BULLISH CANDLE") else "BULLISH BOS" if r["bos"]!="BULLISH BOS" else "BULLISH RETEST")
    elif b=="SELL": trig="🟡 WAIT FOR " + ("BEARISH SWEEP" if r["liquidity"]!="BEARISH SWEEP" else "BEARISH CANDLE" if r["candle_confirmation"] not in ("BEARISH ENGULFING","BEARISH CANDLE") else "BEARISH BOS" if r["bos"]!="BEARISH BOS" else "BEARISH RETEST")
    else: trig="🟡 WAIT FOR DIRECTION"
    msg += f"⏳ *ENTRY TRIGGER*\n{trig}\n\n🟡 *ENTRY / WATCH ZONE*\n`{r['entry_low']:,.2f} – {r['entry_high']:,.2f}`\n\n📉 *SWING LOW*\n`{r['swing_low']:,.2f}`\n\n📈 *SWING HIGH*\n`{r['swing_high']:,.2f}`\n\n"

    if d in ("BUY","SELL"):
        msg += f"🛑 *STOP LOSS*\n`{r['sl']:,.2f}`\n\n🎯 *TP1*\n`{r['tp1']:,.2f}`\n\n🎯 *TP2*\n`{r['tp2']:,.2f}`\n\n"

    msg += "🧠 *ANALYSIS*\n" + "".join(f"• {x}\n" for x in r["reasons"])
    if d=="WAIT":
        msg += "\n⏳ *BELUM LENGKAP*\n" + "".join(f"• Tunggu {x}\n" for x in r["missing"])
    msg += f"\n📡 *DATA SOURCE*\n15M: `{r['source_15m']}`\n1H: `{r['source_1h']}`\n\n🚫 Tiada auto-trading.\n⚠️ Technical signal sahaja. Bukan jaminan profit."
    return msg

# ---------------- TELEGRAM ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *GOLD & BTC SIGNAL BOT V7.2*\n\n"
        "/price - Harga Gold & BTC\n"
        "/signal gold - Signal Gold\n"
        "/signal btc - Signal Bitcoin\n"
        "/news - News monitor\n\n"
        "📊 15M + 1H | EMA RSI ADX ATR\n"
        "💧 Liquidity | 🕯 Candle | 📐 BOS | 🔄 Retest\n"
        "🎯 Entry Zone / SL / TP\n"
        "🔄 Multi-range candle fallback\n"
        "🚫 Tiada auto-trading",
        parse_mode="Markdown"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📈 *HARGA SEMASA V7.2*\n\n"
    op, reason = gold_market_status()
    if not op:
        text += f"🥇 *Gold XAUUSD*\n🔴 MARKET CLOSED\nStatus: `{reason}`\n\n"
    else:
        p,s = get_live_price("gold")
        text += f"🥇 *Gold XAUUSD*\n`${p:,.2f}`\nSource: `{s}`\n\n" if p else "🥇 *Gold XAUUSD*\n❌ Harga tidak tersedia\n\n"
    p,s = get_live_price("btc")
    text += f"₿ *Bitcoin BTC*\n`${p:,.2f}`\nSource: `{s}`" if p else "₿ *Bitcoin BTC*\n❌ Harga tidak tersedia"
    await update.message.reply_text(text, parse_mode="Markdown")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Pilih asset:\n/signal gold\n/signal btc"); return
    asset = context.args[0].lower()
    if asset not in ("gold","btc"):
        await update.message.reply_text("❌ Asset tidak disokong.\n/signal gold\n/signal btc"); return
    status = await update.message.reply_text("🧠 *SIGNAL V7.2*\n\n📡 Mengambil data...\n🔄 Multi-source fallback aktif...\n⏳ Sila tunggu...", parse_mode="Markdown")
    try:
        await status.edit_text(format_signal(asset, analyze_asset(asset)), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Signal error")
        await status.edit_text(f"❌ *SIGNAL ERROR*\n\n`{str(e)}`", parse_mode="Markdown")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📰 *NEWS MONITOR V7.2*\n\n"
        "🥇 GOLD: USD Index, Federal Reserve, CPI, NFP, Interest Rate\n\n"
        "₿ BTC: ETF Flow, Funding Rate, BTC Dominance, US Macro Data\n\n"
        "⚠️ News engine belum live.",
        parse_mode="Markdown"
    )

async def error_handler(update, context):
    logger.error("Telegram error:", exc_info=context.error)

def main():
    print("==========================================")
    print("🤖 GOLD & BTC SIGNAL BOT V7.2")
    print("==========================================")
    if not TOKEN:
        print("❌ BOT_TOKEN TIDAK DIJUMPAI")
        print("Set Railway Variable: BOT_TOKEN = token BotFather")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("news", news))
    app.add_error_handler(error_handler)
    print("🚀 V7.2 BOT AKTIF!")
    print("🔄 15M fallback: 5d -> 1mo -> 3mo")
    print("🔄 1H fallback: 1mo -> 3mo -> 6mo")
    print("🚫 No auto trading")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
