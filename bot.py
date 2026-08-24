import os, logging, requests, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
TWELVE_KEY = os.getenv("TWELVE_API_KEY", "")
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
HISTORY_FILE = "signal_history.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Safari/537.36"
})

# ============================================================
# MARKET STATUS
# ============================================================

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

def get_session_name():
    now = datetime.now(MY_TZ)
    h = now.hour
    if 8 <= h < 17:
        return "LONDON"
    if 13 <= h < 22:
        return "NEW YORK"
    if 0 <= h < 9:
        return "TOKYO"
    return "SYDNEY"

# ============================================================
# SIGNAL HISTORY
# ============================================================

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_history(record):
    try:
        history = load_history()
        history.append(record)
        history = history[-50:]
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        logger.warning("Save history error: %s", e)

def get_stats():
    history = load_history()
    if not history:
        return None
    total = len(history)
    buy = sum(1 for h in history if h.get("direction") == "BUY")
    sell = sum(1 for h in history if h.get("direction") == "SELL")
    wait = sum(1 for h in history if h.get("direction") == "WAIT")
    return {"total": total, "buy": buy, "sell": sell, "wait": wait}

# ============================================================
# TWELVE DATA - XAUUSD SEBENAR
# ============================================================

def twelvedata_candles(symbol, interval="15min", outputsize=200):
    if not TWELVE_KEY:
        return []
    url = "https://api.twelvedata.com/time_series"
    try:
        r = SESSION.get(url, params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": TWELVE_KEY
        }, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("status") == "error":
            logger.warning("TwelveData %s: %s", symbol, data.get("message"))
            return []
        values = data.get("values", [])
        candles = []
        for item in reversed(values):
            try:
                candles.append({
                    "time": item.get("datetime"),
                    "open": float(item.get("open", 0)),
                    "high": float(item.get("high", 0)),
                    "low": float(item.get("low", 0)),
                    "close": float(item.get("close", 0)),
                    "volume": float(item.get("volume", 0) or 0)
                })
            except (TypeError, ValueError):
                continue
        logger.info("TwelveData %s: %d candles", symbol, len(candles))
        return candles
    except Exception as e:
        logger.warning("TwelveData %s error: %s", symbol, e)
        return []

# ============================================================
# ALPHA VANTAGE - XAUUSD FALLBACK
# ============================================================

def alphavantage_candles(symbol="XAU", interval="15min"):
    key = os.getenv("ALPHA_KEY", "demo")
    url = "https://www.alphavantage.co/query"
    try:
        r = SESSION.get(url, params={
            "function": "FX_INTRADAY",
            "from_symbol": "XAU",
            "to_symbol": "USD",
            "interval": interval,
            "outputsize": "full",
            "apikey": key
        }, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        key_name = "Time Series FX (" + interval + ")"
        ts = data.get(key_name, {})
        if not ts:
            return []
        candles = []
        for dt in sorted(ts.keys()):
            try:
                item = ts[dt]
                candles.append({
                    "time": dt,
                    "open": float(item.get("1. open", 0)),
                    "high": float(item.get("2. high", 0)),
                    "low": float(item.get("3. low", 0)),
                    "close": float(item.get("4. close", 0)),
                    "volume": 0
                })
            except (TypeError, ValueError):
                continue
        logger.info("AlphaVantage %s: %d candles", symbol, len(candles))
        return candles
    except Exception as e:
        logger.warning("AlphaVantage error: %s", e)
        return []

# ============================================================
# BINANCE CANDLES
# ============================================================

def binance_candles(symbol, interval="15m", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    try:
        r = SESSION.get(url, params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }, timeout=15)
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
        logger.info("Binance %s: %d candles", symbol, len(candles))
        return candles
    except Exception as e:
        logger.warning("Binance %s error: %s", symbol, e)
        return []

# ============================================================
# COINGECKO
# ============================================================

def coingecko_ohlc(coin_id, days=90):
    url = "https://api.coingecko.com/api/v3/coins/" + coin_id + "/ohlc"
    try:
        r = SESSION.get(url, params={
            "vs_currency": "usd",
            "days": days
        }, timeout=15)
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
                    "volume": 0
                })
            except (IndexError, TypeError, ValueError):
                continue
        logger.info("CoinGecko %s: %d candles", coin_id, len(candles))
        return candles
    except Exception as e:
        logger.warning("CoinGecko error: %s", e)
        return []

# ============================================================
# REAL GOLD PRICE
# ============================================================

def get_real_gold_price():
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
                p = parser(r)
                if p and float(p) > 0:
                    return float(p), url.split("/")[2]
        except Exception as e:
            logger.warning("Gold price error: %s", e)
    return None, None

# ============================================================
# GOLD CANDLES SCALED FROM PAXG
# ============================================================

def gold_candles_scaled():
    paxg = binance_candles("PAXGUSDT", "15m", 200)
    if len(paxg) < 20:
        paxg = binance_candles("PAXGUSDT", "1h", 200)
    if len(paxg) < 20:
        return [], None
    real_gold, _ = get_real_gold_price()
    if real_gold is None:
        return paxg, "PAXG-NoScale"
    paxg_last = paxg[-1]["close"]
    if paxg_last <= 0:
        return paxg, "PAXG-NoScale"
    ratio = real_gold / paxg_last
    scaled = []
    for c in paxg:
        scaled.append({
            "time": c["time"],
            "open": c["open"] * ratio,
            "high": c["high"] * ratio,
            "low": c["low"] * ratio,
            "close": c["close"] * ratio,
            "volume": c["volume"]
        })
    logger.info("Gold scaled: last=%.2f real=%.2f ratio=%.6f",
                scaled[-1]["close"], real_gold, ratio)
    return scaled, "XAUUSD-Spot"

# ============================================================
# GET CANDLES - MULTI SOURCE
# ============================================================

def get_candles(asset, timeframe="15m", minimum=20):
    if asset == "btc":
        sources = [
            ("Binance 15m", lambda: (binance_candles("BTCUSDT", "15m", 200), "Binance-15m")),
            ("Binance 1h", lambda: (binance_candles("BTCUSDT", "1h", 200), "Binance-1h")),
            ("CoinGecko BTC", lambda: (coingecko_ohlc("bitcoin", 90), "CoinGecko")),
        ]
    elif asset == "gold":
        if timeframe == "1h":
            sources = [
                ("TwelveData 1h", lambda: (twelvedata_candles("XAU/USD", "1h", 200), "TwelveData-1h")),
                ("Gold Scaled 1h", lambda: (binance_candles("PAXGUSDT", "1h", 200), "PAXG-1h")),
                ("Gold Scaled 15m", lambda: gold_candles_scaled()),
            ]
        else:
            sources = [
                ("TwelveData 15m", lambda: (twelvedata_candles("XAU/USD", "15min", 200), "TwelveData-15m")),
                ("Gold Scaled", lambda: gold_candles_scaled()),
                ("CoinGecko PAXG", lambda: (coingecko_ohlc("pax-gold", 90), "CoinGecko-PAXG")),
            ]
    else:
        return [], None

    for source_name, source_func in sources:
        try:
            result = source_func()
            if isinstance(result, tuple):
                candles, src = result
            else:
                candles, src = result, source_name
            if candles and len(candles) >= minimum:
                logger.info("%s %s from %s: %d candles", asset, timeframe, src, len(candles))
                return candles, src
            logger.warning("%s from %s: only %d candles", asset, source_name, len(candles) if candles else 0)
        except Exception as e:
            logger.warning("%s from %s failed: %s", asset, source_name, e)
            continue

    return [], None

# ============================================================
# LIVE PRICE
# ============================================================

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
                    return float(price), url.split("/")[2]
        except Exception as e:
            logger.warning("Price API error: %s", e)
    return None, None

# ============================================================
# NEWS ENGINE - FOREXFACTORY
# ============================================================

def get_forex_news():
    try:
        now = datetime.now(MY_TZ)
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r = SESSION.get(url, timeout=10)
        if r.status_code != 200:
            return []
        events = r.json()
        relevant = []
        for event in events:
            impact = event.get("impact", "").upper()
            currency = event.get("country", "").upper()
            title = event.get("title", "")
            date_str = event.get("date", "")
            if impact == "HIGH" and currency in ("USD", "XAU"):
                relevant.append({
                    "title": title,
                    "impact": impact,
                    "currency": currency,
                    "date": date_str
                })
        return relevant[:5]
    except Exception as e:
        logger.warning("ForexFactory news error: %s", e)
        return []

def news_risk_warning(news):
    if not news:
        return False, ""
    now = datetime.now(MY_TZ)
    for event in news:
        try:
            date_str = event.get("date", "")
            if not date_str:
                continue
            event_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            event_local = event_dt.astimezone(MY_TZ)
            diff = abs((event_local - now).total_seconds() / 60)
            if diff <= 30:
                return True, "⚠️ HIGH IMPACT NEWS dalam " + str(int(diff)) + " minit: " + event.get("title", "")
        except Exception:
            continue
    return False, ""

# ============================================================
# INDICATORS
# ============================================================

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

def rsi_divergence(candles, rsi_values, lookback=10):
    if len(candles) < lookback or len(rsi_values) < lookback:
        return "NONE"
    prices = [c["close"] for c in candles[-lookback:]]
    rsis = rsi_values[-lookback:]
    if prices[-1] < prices[0] and rsis[-1] > rsis[0]:
        return "BULLISH DIVERGENCE"
    if prices[-1] > prices[0] and rsis[-1] < rsis[0]:
        return "BEARISH DIVERGENCE"
    return "NONE"

def atr(c, n=14):
    if len(c) < n + 1:
        return None
    tr = []
    for i in range(1, len(c)):
        x, p = c[i], c[i-1]
        tr.append(max(x["high"]-x["low"],
                      abs(x["high"]-p["close"]),
                      abs(x["low"]-p["close"])))
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
        hd = x["high"] - p["high"]
        ld = p["low"] - x["low"]
        tr.append(max(x["high"]-x["low"],
                      abs(x["high"]-p["close"]),
                      abs(x["low"]-p["close"])))
        pdm.append(hd if hd > ld and hd > 0 else 0)
        mdm.append(ld if ld > hd and ld > 0 else 0)
    ta = sum(tr[:n])/n
    pa = sum(pdm[:n])/n
    ma = sum(mdm[:n])/n
    dx = []
    for i in range(n, len(tr)):
        ta = ((ta*(n-1))+tr[i])/n
        pa = ((pa*(n-1))+pdm[i])/n
        ma = ((ma*(n-1))+mdm[i])/n
        if ta == 0:
            continue
        pdi = 100*pa/ta
        mdi = 100*ma/ta
        if pdi+mdi == 0:
            continue
        dx.append(100*abs(pdi-mdi)/(pdi+mdi))
    return sum(dx[-n:])/n if len(dx) >= n else None

# ============================================================
# STRUCTURE
# ============================================================

def get_swings(c, n=30):
    if not c:
        return None, None
    x = c[-min(n, len(c)):]
    return min(z["low"] for z in x), max(z["high"] for z in x)

def market_structure(c):
    if len(c) < 20:
        return "NEUTRAL"
    a = c[-20:-10]
    b = c[-10:]
    ah = max(x["high"] for x in a)
    bh = max(x["high"] for x in b)
    al = min(x["low"] for x in a)
    bl = min(x["low"] for x in b)
    if bh > ah and bl > al:
        return "BULLISH"
    if bh < ah and bl < al:
        return "BEARISH"
    return "NEUTRAL"

def market_structure_4h(c4h):
    if len(c4h) < 20:
        return "NEUTRAL"
    a = c4h[-20:-10]
    b = c4h[-10:]
    ah = max(x["high"] for x in a)
    bh = max(x["high"] for x in b)
    al = min(x["low"] for x in a)
    bl = min(x["low"] for x in b)
    if bh > ah and bl > al:
        return "BULLISH"
    if bh < ah and bl < al:
        return "BEARISH"
    return "NEUTRAL"

def candle_confirmation(c):
    if len(c) < 3:
        return "NONE"
    p = c[-2]
    x = c[-1]
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

def liquidity_sweep(c, window=20):
    if len(c) < window + 1:
        return "NONE", None
    x = c[-1]
    prev = c[-(window+1):-1]
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

def calculate_bias(e20, e50, structure, h1, trend_4h, rv, divergence):
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
    if trend_4h == "BULLISH":
        buy += 2
    elif trend_4h == "BEARISH":
        sell += 2
    if rv is not None:
        if 50 <= rv < 70:
            buy += 1
        elif 30 < rv < 50:
            sell += 1
    if divergence == "BULLISH DIVERGENCE":
        buy += 1
    elif divergence == "BEARISH DIVERGENCE":
        sell += 1
    if buy >= sell+2:
        return "BUY", buy, sell
    if sell >= buy+2:
        
