import os, logging, requests, json
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
HISTORY_FILE = "/tmp/history.json"
ALERT_STATE_FILE = "/tmp/alert_state.json"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 13) Chrome/120"})

last_signal_state = {}


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


def load_alert_state():
    global last_signal_state
    try:
        if os.path.exists(ALERT_STATE_FILE):
            with open(ALERT_STATE_FILE) as f:
                last_signal_state = json.load(f)
    except Exception:
        last_signal_state = {}


def save_alert_state():
    try:
        with open(ALERT_STATE_FILE, "w") as f:
            json.dump(last_signal_state, f)
    except Exception as e:
        logger.warning("save alert state error: %s", e)


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
    from helpers import SESSION
    TWELVE_KEY = os.getenv("TWELVE_API_KEY", "")
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
