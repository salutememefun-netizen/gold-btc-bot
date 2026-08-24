import os, logging, requests, json
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
TWELVE_KEY = os.getenv("TWELVE_API_KEY", "")
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
HISTORY_FILE = "/tmp/history.json"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 13) Chrome/120"})


def gold_market_open():
    now = datetime.now(MY_TZ)
    wd, mins = now.weekday(), now.hour * 60 + now.minute
    if wd == 5: return False, "WEEKEND"
    if wd == 6 and mins < 360: return False, "WEEKEND"
    if 300 <= mins < 360: return False, "DAILY BREAK"
    return True, "OPEN"


def get_session():
    h = datetime.now(MY_TZ).hour
    if 15 <= h < 24: return "NEW YORK"
    if 8 <= h < 17: return "LONDON"
    if 2 <= h < 11: return "TOKYO"
    return "SYDNEY"


def save_history(asset, direction, price, score):
    try:
        data = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                data = json.load(f)
        data.append({"time": datetime.now(MY_TZ).strftime("%d/%m %H:%M"),
                     "asset": asset, "direction": direction,
                     "price": price, "score": score})
        data = data[-50:]
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning("history error: %s", e)


def get_stats(asset):
    try:
        if not os.path.exists(HISTORY_FILE):
            return None
        with open(HISTORY_FILE) as f:
            data = json.load(f)
        d = [x for x in data if x.get("asset") == asset]
        if not d:
            return None
        return {
            "total": len(d),
            "buy": sum(1 for x in d if x.get("direction") == "BUY"),
            "sell": sum(1 for x in d if x.get("direction") == "SELL"),
            "wait": sum(1 for x in d if x.get("direction") == "WAIT")
        }
    except Exception:
        return None


def binance_candles(symbol, interval="15m", limit=200):
    try:
        r = SESSION.get("https://api.binance.com/api/v3/klines",
                        params={"symbol": symbol, "interval": interval, "limit": limit},
                        timeout=15)
        if r.status_code != 200:
            return []
        out = []
        for x in r.json():
            try:
                out.append({"time": x[0], "open": float(x[1]), "high": float(x[2]),
                            "low": float(x[3]), "close": float(x[4]), "volume": float(x[7])})
            except Exception:
                continue
        return out
    except Exception as e:
        logger.warning("binance %s: %s", symbol, e)
        return []


def coingecko_ohlc(coin, days=90):
    try:
        r = SESSION.get("https://api.coingecko.com/api/v3/coins/" + coin + "/ohlc",
                        params={"vs_currency": "usd", "days": days}, timeout=15)
        if r.status_code != 200:
            return []
        out = []
        for x in r.json():
            try:
                out.append({"time": x[0], "open": float(x[1]), "high": float(x[2]),
                            "low": float(x[3]), "close": float(x[4]), "volume": 0})
            except Exception:
                continue
        return out
    except Exception as e:
        logger.warning("coingecko %s: %s", coin, e)
        return []


def twelvedata_candles(symbol, interval="15min", size=200):
    if not TWELVE_KEY:
        return []
    try:
        r = SESSION.get("https://api.twelvedata.com/time_series",
                        params={"symbol": symbol, "interval": interval,
                                "outputsize": size, "apikey": TWELVE_KEY},
                        timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("status") == "error":
            return []
        out = []
        for x in reversed(data.get("values", [])):
            try:
                out.append({"time": x.get("datetime"), "open": float(x.get("open", 0)),
                            "high": float(x.get("high", 0)), "low": float(x.get("low", 0)),
                            "close": float(x.get("close", 0)), "volume": 0})
            except Exception:
                continue
        return out
    except Exception as e:
        logger.warning("twelvedata %s: %s", symbol, e)
        return []


def get_gold_price():
    for url, fn in [
        ("https://api.metals.live/v1/spot/gold", lambda r: r.json().get("price")),
        ("https://api.gold-api.com/price/XAU", lambda r: r.json().get("price")),
    ]:
        try:
            r = SESSION.get(url, timeout=10)
            if r.status_code == 200:
                p = fn(r)
                if p and float(p) > 0:
                    return float(p), url.split("/")[2]
        except Exception:
            pass
    return None, None


def gold_candles():
    paxg = binance_candles("PAXGUSDT", "15m", 200)
    if len(paxg) < 20:
        paxg = binance_candles("PAXGUSDT", "1h", 200)
    if len(paxg) < 20:
        return [], None
    real, _ = get_gold_price()
    if not real:
        return paxg, "PAXG"
    ratio = real / paxg[-1]["close"]
    out = []
    for c in paxg:
        out.append({"time": c["time"], "open": c["open"] * ratio,
                    "high": c["high"] * ratio, "low": c["low"] * ratio,
                    "close": c["close"] * ratio, "volume": c["volume"]})
    return out, "XAUUSD-Scaled"


def get_candles(asset, tf="15m", minimum=20):
    if asset == "btc":
        sources = [
            lambda: (binance_candles("BTCUSDT", "15m", 200), "Binance-15m"),
            lambda: (binance_candles("BTCUSDT", "1h", 200), "Binance-1h"),
            lambda: (coingecko_ohlc("bitcoin", 90), "CoinGecko"),
        ]
    else:
        if tf in ("1h", "4h"):
            sources = [
                lambda: (twelvedata_candles("XAU/USD", "1h", 200), "Twelve-1h"),
                lambda: (binance_candles("PAXGUSDT", "1h", 200), "PAXG-1h"),
                lambda: gold_candles(),
            ]
        else:
            sources = [
                lambda: (twelvedata_candles("XAU/USD", "15min", 200), "Twelve-15m"),
                lambda: gold_candles(),
                lambda: (coingecko_ohlc("pax-gold", 90), "CoinGecko-PAXG"),
            ]
    for fn in sources:
        try:
            result = fn()
            candles, src = result if isinstance(result, tuple) else (result, "unknown")
            if candles and len(candles) >= minimum:
                return candles, src
        except Exception as e:
            logger.warning("candle source failed: %s", e)
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
            ("https://api.metals.live/v1/spot/gold", lambda r: r.json().get("price")),
            ("https://api.gold-api.com/price/XAU", lambda r: r.json().get("price")),
        ]
    for url, fn in apis:
        try:
            r = SESSION.get(url, timeout=10)
            if r.status_code == 200:
                p = fn(r)
                if p and float(p) > 0:
                    return float(p), url.split("/")[2]
        except Exception:
            pass
    return None, None


def get_news():
    try:
        r = SESSION.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        if r.status_code != 200:
            return []
        out = []
        for e in r.json():
            if str(e.get("impact", "")).upper() == "HIGH" and str(e.get("country", "")).upper() in ("USD", "XAU"):
                out.append({"title": e.get("title", ""), "date": e.get("date", "")})
        return out[:5]
    except Exception:
        return []


def check_news_risk(news):
    now = datetime.now(MY_TZ)
    for e in news:
        try:
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(MY_TZ)
            diff = abs((dt - now).total_seconds() / 60)
            if diff <= 30:
                return True, "HIGH IMPACT NEWS dalam " + str(int(diff)) + " min: " + e["title"]
        except Exception:
            pass
    return False, ""


def ema(v, n):
    if len(v) < n:
        return None
    k = 2 / (n + 1)
    x = sum(v[:n]) / n
    for p in v[n:]:
        x = (p - x) * k + x
    return x


def rsi_calc(v, n=14):
    if len(v) < n + 1:
        return None
    g, l = [], []
    for i in range(1, len(v)):
        d = v[i] - v[i-1]
        g.append(max(d, 0))
        l.append(max(-d, 0))
    ag, al = sum(g[:n])/n, sum(l[:n])/n
    for i in range(n, len(g)):
        ag = ((ag*(n-1))+g[i])/n
        al = ((al*(n-1))+l[i])/n
    if al == 0:
        return 100.0
    return 100 - 100/(1 + ag/al)


def atr_calc(c, n=14):
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


def adx_calc(c, n=14):
    if len(c) < n*2+1:
        return None
    tr, pdm, mdm = [], [], []
    for i in range(1, len(c)):
        x, p = c[i], c[i-1]
        hd = x["high"] - p["high"]
        ld = p["low"] - x["low"]
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


def rsi_divergence(c, lb=10):
    if len(c) < lb + 14:
        return "NONE"
    closes = [x["close"] for x in c]
    rv = []
    for i in range(len(closes)):
        if i >= 14:
            rv.append(rsi_calc(closes[max(0, i-28):i+1]))
        else:
            rv.append(None)
    rr = [x for x in rv[-lb:] if x is not None]
    if len(rr) < 2:
        return "NONE"
    pp = [x["close"] for x in c[-len(rr):]]
    if pp[-1] < pp[0] and rr[-1] > rr[0]:
        return "BULLISH DIV"
    if pp[-1] > pp[0] and rr[-1] < rr[0]:
        return "BEARISH DIV"
    return "NONE"


def get_swings(c, n=30):
    if not c:
        return None, None
    x = c[-min(n, len(c)):]
    return min(z["low"] for z in x), max(z["high"] for z in x)


def structure(c):
    if len(c) < 20:
        return "NEUTRAL"
    a, b = c[-20:-10], c[-10:]
    if max(x["high"] for x in b) > max(x["high"] for x in a) and min(x["low"] for x in b) > min(x["low"] for x in a):
        return "BULLISH"
    if max(x["high"] for x in b) < max(x["high"] for x in a) and min(x["low"] for x in b) < min(x["low"] for x in a):
        return "BEARISH"
    return "NEUTRAL"


def candle_conf(c):
    if len(c) < 3:
        return "NONE"
    p, x = c[-2], c[-1]
    xb = x["close"] > x["open"]
    xa = x["close"] < x["open"]
    if p["close"] < p["open"] and xb and x["open"] <= p["close"] and x["close"] >= p["open"]:
        return "BULLISH ENGULFING"
    if p["close"] > p["open"] and xa and x["open"] >= p["close"] and x["close"] <= p["open"]:
        return "BEARISH ENGULFING"
    rng = x["high"] - x["low"]
    body = abs(x["close"] - x["open"])
    if rng > 0 and body / rng >= 0.65:
        return "BULLISH CANDLE" if xb else "BEARISH CANDLE"
    return "NONE"


def liq_sweep(c, w=20):
    if len(c) < w + 1:
        return "NONE", None
    x = c[-1]
    prev = c[-(w+1):-1]
    hi = max(z["high"] for z in prev)
    lo = min(z["low"] for z in prev)
    if x["low"] < lo and x["close"] > lo:
        return "BULLISH SWEEP", lo
    if x["high"] > hi and x["close"] < hi:
        return "BEARISH SWEEP", hi
    return "NONE", None


def bos_detect(c):
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


def retest_detect(c, bos, bp, av):
    if bos == "NONE" or bp is None or av is None:
        return "NONE", None
    x = c[-1]
    tol = av * 0.20
    if bos == "BULLISH BOS" and x["low"] <= bp + tol and x["close"] > bp:
        return "BULLISH RETEST", bp
    if bos == "BEARISH BOS" and x["high"] >= bp - tol and x["close"] < bp:
        return "BEARISH RETEST", bp
    return "NONE", None


def calc_bias(e20, e50, st, h1, h4, rv, div):
    buy = sell = 0
    if e20 is not None and e50 is not None:
        if e20 > e50: buy += 1
        elif e20 < e50: sell += 1
    if st == "BULLISH": buy += 2
    elif st == "BEARISH": sell += 2
    if h1 == "BULLISH": buy += 2
    elif h1 == "BEARISH": sell += 2
    if h4 == "BULLISH": buy += 2
    elif h4 == "BEARISH": sell += 2
    if rv is not None:
        if 50 <= rv < 70: buy += 1
        elif 30 < rv < 50: sell += 1
    if div == "BULLISH DIV": buy += 1
    elif div == "BEARISH DIV": sell += 1
    if buy >= sell + 2: return "BUY", buy, sell
    if sell >= buy + 2: return "SELL", buy, sell
    return "NEUTRAL", buy, sell


def build_zone(price, av, ref=None):
    av = av if av and av > 0 else price * 0.005
    ref = ref if ref is not None else price
    return ref - av * 0.20, ref + av * 0.20


def analyze(asset):
    if asset == "gold":
        opened, reason = gold_market_open()
        if not opened:
            return {"market_open": False, "market_reason": reason}

    c15, s15 = get_candles(asset, "15m", 20)
    c1h, s1h = get_candles(asset, "1h", 20)
    c4h, s4h = get_candles(asset, "4h", 20)

    if len(c15) < 20:
        return None

    closes = [x["close"] for x in c15]

    if asset == "gold":
        real, _ = get_gold_price()
        price = real if real else closes[-1]
        scale = real / closes[-1] if real and closes[-1] > 0 else 1.0
    else:
        price = closes[-1]
        scale = 1.0

    e20 = ema(closes, 20)
    e50 = ema(closes, 50) if len(closes) >= 50 else None
    rv = rsi_calc(closes)
    av = atr_calc(c15)
    ax = adx_calc(c15)
    div = rsi_divergence(c15)
    st = structure(c15)
    slw_r, shw_r = get_swings(c15, 30)
    slw = slw_r * scale if slw_r else None
    shw = shw_r * scale if shw_r else None

    def trend(cx):
        if len(cx) < 20:
            return "NEUTRAL"
        hc = [x["close"] for x in cx]
        a = ema(hc, 20)
        b = ema(hc, 50) if len(hc) >= 50 else None
        if a and b:
            return "BULLISH" if a > b else "BEARISH"
        return "NEUTRAL"

    h1 = trend(c1h)
    h4 = trend(c4h)

    news = get_news()
    news_risk, news_msg = check_news_risk(news)

    bias, bp, sp = calc_bias(e20, e50, st, h1, h4, rv, div)
    liq, lp = liq_sweep(c15, 20)
    candle = candle_conf(c15)
    bos, bosp = bos_detect(c15)
    retest, retp = retest_detect(c15, bos, bosp, av)

    if scale != 1.0:
        if lp: lp = lp * scale
        if bosp: bosp = bosp * scale

    score = 0
    if bias == "BUY":
        if liq == "BULLISH SWEEP": score += 25
        if candle in ("BULLISH ENGULFING", "BULLISH CANDLE"): score += 20
        if bos == "BULLISH BOS": score += 25
        if retest == "BULLISH RETEST": score += 30
    elif bias == "SELL":
        if liq == "BEARISH SWEEP": score += 25
        if candle in ("BEARISH ENGULFING", "BEARISH CANDLE"): score += 20
        if bos == "BEARISH BOS": score += 25
        if retest == "BEARISH RETEST": score += 30

    direction = "WAIT"
    if not news_risk:
        if bias == "BUY":
            full = (liq == "BULLISH SWEEP" and
                    candle in ("BULLISH ENGULFING", "BULLISH CANDLE") and
                    bos == "BULLISH BOS" and retest == "BULLISH RETEST")
            part = (score >= 75 and
                    candle in ("BULLISH ENGULFING", "BULLISH CANDLE") and
                    bos == "BULLISH BOS" and retest == "BULLISH RETEST")
            if full or part:
                direction = "BUY"
        elif bias == "SELL":
            full = (liq == "BEARISH SWEEP" and
                    candle in ("BEARISH ENGULFING", "BEARISH CANDLE") and
                    bos == "BEARISH BOS" and retest == "BEARISH RETEST")
            part = (score >= 75 and
                    candle in ("BEARISH ENGULFING", "BEARISH CANDLE") and
                    bos == "BEARISH BOS" and retest == "BEARISH RETEST")
            if full or part:
                direction = "SELL"

    confidence = (min(95, int(55 + score * 0.40)) if direction in ("BUY", "SELL")
                  else min(59, int(40 + abs(bp - sp) * 4 + score * 0.10)))

    safe_av = (av * scale) if av else price * 0.005
    ref = bosp if bosp else lp
    zl, zh = build_zone(price, safe_av, ref)

    sl = tp1 = tp2 = rr1 = rr2 = None
    if direction == "BUY":
        protect = lp if lp else (slw if slw else price * 0.99)
        sl = protect - safe_av * 0.30
        risk = max(price - sl, safe_av)
        tp1 = price + risk * 1.5
        tp2 = price + risk * 2.5
        rr1, rr2 = 1.5, 2.5
    elif direction == "SELL":
        protect = lp if lp else (shw if shw else price * 1.01)
        sl = protect + safe_av * 0.30
        risk = max(sl - price, safe_av)
        tp1 = price - risk * 1.5
        tp2 = price - risk * 2.5
        rr1, rr2 = 1.5, 2.5

    save_history(asset, direction, price, score)

    reasons = []
    if e20 and e50:
        reasons.append("EMA20 " + ("atas" if e20 > e50 else "bawah") + " EMA50")
    if st != "NEUTRAL": reasons.append("Structure 15M " + st)
    if h1 != "NEUTRAL": reasons.append("Trend 1H " + h1)
    if h4 != "NEUTRAL": reasons.append("Trend 4H " + h4)
    if div != "NONE": reasons.append(div)
    if liq != "NONE": reasons.append(liq)
    if candle != "NONE": reasons.append(candle)
    if bos != "NONE": reasons.append(bos)
    if retest != "NONE": reasons.append(retest)
    if news_risk: reasons.append("NEWS RISK: " + news_msg)
    if not reasons: reasons.append("Belum ada confirmation")

    missing = []
    if direction == "WAIT":
        if bias == "BUY":
            if candle not in ("BULLISH ENGULFING", "BULLISH CANDLE"):
                missing.append("Bullish candle")
            if bos != "BULLISH BOS":
                missing.append("Bullish BOS")
            if retest != "BULLISH RETEST":
                missing.append("Bullish retest")
            if liq != "BULLISH SWEEP":
                missing.append("Bullish sweep (optional)")
        elif bias == "SELL":
            if candle not in ("BEARISH ENGULFING", "BEARISH CANDLE"):
                missing.append("Bearish candle")
            if bos != "BEARISH BOS":
                missing.append("Bearish BOS")
            if retest != "BEARISH RETEST":
                missing.append("Bearish retest")
            if liq != "BEARISH SWEEP":
                missing.append("Bearish sweep (optional)")
        else:
            missing.append("Directional bias")

    return {
        "market_open": True,
        "price": price,
        "direction": direction,
        "bias": bias,
        "confidence": confidence,
        "score": score,
        "ema20": e20,
        "ema50": e50,
        "rsi": rv,
        "atr": av,
        "adx": ax,
        "divergence": div,
        "structure": st,
        "h1": h1,
        "h4": h4,
        "liq": liq,
        "liq_price": lp,
        "candle": candle,
        "bos": bos,
        "bos_price": bosp,
        "retest": retest,
        "retest_price": retp,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "rr1": rr1,
        "rr2": rr2,
        "zone_low": zl,
        "zone_high": zh,
        "swing_low": slw,
        "swing_high": shw,
        "reasons": reasons,
        "missing": missing,
        "news": news,
        "news_risk": news_risk,
        "news_msg": news_msg,
        "source": s15,
        "session": get_session()
    }


def fmt(asset, d):
    if not d:
        return "Data tidak cukup untuk analisis."
    if not d.get("market_open"):
        return "Market TUTUP: " + d.get("market_reason", "")

    name = "GOLD (XAU/USD)" if asset == "gold" else "BITCOIN (BTC/USD)"
    direction = d["direction"]
    bias = d["bias"]
    price = d["price"]
    confidence = d["confidence"]
    score = d["score"]

    if direction == "BUY":
        signal_line = "🟢 SIGNAL: BUY"
    elif direction == "SELL":
        signal_line = "🔴 SIGNAL: SELL"
    else:
        signal_line = "⏳ SIGNAL: TUNGGU"

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 " + name,
        "━━━━━━━━━━━━━━━━━━━━",
        signal_line,
        "💰 Harga: " + str(round(price, 2)),
        "🎯 Bias: " + bias,
        "📈 Score: " + str(score) + "/100",
        "🔒 Confidence: " + str(confidence) + "%",
        "🕐 Session: " + d.get("session", ""),
        "📡 Source: " + str(d.get("source", "")),
        "",
    ]

    if d.get("rsi") is not None:
        lines.append("RSI: " + str(round(d["rsi"], 1)))
    if d.get("adx") is not None:
        lines.append("ADX: " + str(round(d["adx"], 1)))
    if d.get("atr") is not None:
        lines.append("ATR: " + str(round(d["atr"], 2)))
    if d.get("divergence") and d["divergence"] != "NONE":
        lines.append("DIV: " + d["divergence"])

    lines.append("")
    lines.append("📋 Sebab:")
    for r in d.get("reasons", []):
        lines.append("  • " + r)

    if d.get("missing"):
        lines.append("")
        lines.append("⏳ Tunggu:")
        for m in d["missing"]:
            lines.append("  • " + m)

    if direction in ("BUY", "SELL"):
        lines.append("")
        lines.append("🎯 Level:")
        if d.get("sl") is not None:
            lines.append("  SL: " + str(round(d["sl"], 2)))
        if d.get("tp1") is not None:
            lines.append("  TP1: " + str(round(d["tp1"], 2)) + " (RR " + str(d.get("rr1", "")) + ")")
        if d.get("tp2") is not None:
            lines.append("  TP2: " + str(round(d["tp2"], 2)) + " (RR " + str(d.get("rr2", "")) + ")")
        if d.get("zone_low") is not None:
            lines.append("  Zone: " + str(round(d["zone_low"], 2)) + " - " + str(round(d["zone_high"], 2)))

    if d.get("news"):
        lines.append("")
        lines.append("📰 News USD minggu ini:")
        for n in d["news"][:3]:
            lines.append("  • " + n.get("title", ""))

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Selamat datang ke Signal Bot!\n\n"
        "Gunakan arahan berikut:\n"
        "/gold - Analisis XAU/USD\n"
        "/btc - Analisis BTC/USD\n"
        "/stats - Statistik signal\n"
        "/help - Bantuan"
    )
    await update.message.reply_text(msg)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 Arahan Bot:\n\n"
        "/gold - Signal analisis GOLD\n"
        "/btc - Signal analisis BTC\n"
        "/stats - Lihat rekod signal\n"
        "/start - Mesej selamat datang"
    )
    await update.message.reply_text(msg)


async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis GOLD...")
    try:
        d = analyze("gold")
        await update.message.reply_text(fmt("gold", d))
    except Exception as e:
        logger.error("gold_cmd error: %s", e)
        await update.message.reply_text("❌ Ralat semasa analisis. Cuba lagi.")


async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis BTC...")
    try:
        d = analyze("btc")
        await update.message.reply_text(fmt("btc", d))
    except Exception as e:
        logger.error("btc_cmd error: %s", e)
        await update.message.reply_text("❌ Ralat semasa analisis. Cuba lagi.")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📊 Statistik Signal\n"]
    for asset in ("gold", "btc"):
        s = get_stats(asset)
        name = "GOLD" if asset == "gold" else "BTC"
        if s:
            lines.append(name + ":")
            lines.append("  Total: " + str(s["total"]))
            lines.append("  BUY: " + str(s["buy"]))
            lines.append("  SELL: " + str(s["sell"]))
            lines.append("  WAIT: " + str(s["wait"]))
        else:
            lines.append(name + ": Tiada rekod")
        lines.append("")
    await update.message.reply_text("\n".join(lines))


def main():
    if not TOKEN:
        logger.error("BOT_TOKEN tidak dijumpai!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("gold", gold_cmd))
    app.add_handler(CommandHandler("btc", btc_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    logger.info("Bot dimulakan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
