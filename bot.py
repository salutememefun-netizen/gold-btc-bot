import os, logging, requests, json, asyncio
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
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})
auto_chats, last_signals = set(), {}

def gmo():
    n = datetime.now(MY_TZ)
    w, m = n.weekday(), n.hour * 60 + n.minute
    if w == 5: return False, "WEEKEND"
    if w == 6 and m < 360: return False, "WEEKEND"
    if 300 <= m < 360: return False, "BREAK"
    return True, "OPEN"

def gs():
    h = datetime.now(MY_TZ).hour
    if 15 <= h < 24: return "NY"
    if 8 <= h < 17: return "LDN"
    if 2 <= h < 11: return "TKY"
    return "SYD"

def sh(d, a, dr, p, s):
    try:
        f = HISTORY_FILE
        data = json.load(open(f)) if os.path.exists(f) else []
        data.append({"time": datetime.now(MY_TZ).strftime("%d/%m %H:%M"), "asset": a, "direction": dr, "price": p, "score": s})
        json.dump(data[-50:], open(f, "w"))
    except Exception as e: logger.warning(e)

def stats(a):
    try:
        if not os.path.exists(HISTORY_FILE): return None
        d = [x for x in json.load(open(HISTORY_FILE)) if x.get("asset") == a]
        if not d: return None
        return {"total": len(d), "buy": sum(1 for x in d if x.get("direction") == "BUY"), "sell": sum(1 for x in d if x.get("direction") == "SELL"), "wait": sum(1 for x in d if x.get("direction") == "WAIT")}
    except: return None

def bc(symb, iv="15m", lim=200):
    try:
        r = SESSION.get("https://api.binance.com/api/v3/klines", params={"symbol": symb, "interval": iv, "limit": lim}, timeout=10)
        if r.status_code != 200: return []
        return [{"time": x[0], "open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[7])} for x in r.json()]
    except Exception as e: logger.warning(e); return []

def cg(coin, days=90):
    try:
        r = SESSION.get(f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc", params={"vs_currency": "usd", "days": days}, timeout=10)
        if r.status_code != 200: return []
        return [{"time": x[0], "open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": 0} for x in r.json()]
    except Exception as e: logger.warning(e); return []

def td(sym, iv="15min", sz=200):
    if not TWELVE_KEY: return []
    try:
        r = SESSION.get("https://api.twelvedata.com/time_series", params={"symbol": sym, "interval": iv, "outputsize": sz, "apikey": TWELVE_KEY}, timeout=10)
        if r.status_code != 200 or r.json().get("status") == "error": return []
        return [{"time": x.get("datetime"), "open": float(x.get("open", 0)), "high": float(x.get("high", 0)), "low": float(x.get("low", 0)), "close": float(x.get("close", 0)), "volume": 0} for x in reversed(r.json().get("values", []))]
    except Exception as e: logger.warning(e); return []

def ggp():
    for u, fn in [("https://api.metals.live/v1/spot/gold", lambda r: r.json().get("price")), ("https://api.gold-api.com/price/XAU", lambda r: r.json().get("price"))]:
        try:
            r = SESSION.get(u, timeout=5)
            if r.status_code == 200:
                p = fn(r)
                if p and float(p) > 0: return float(p), u.split("/")[2]
        except: pass
    return None, None

def gc():
    p = bc("PAXGUSDT", "15m", 200)
    if len(p) < 20: p = bc("PAXGUSDT", "1h", 200)
    if len(p) < 20: return [], None
    real, _ = ggp()
    if not real: return p, "PAXG"
    r = real / p[-1]["close"]
    return [{"time": c["time"], "open": c["open"] * r, "high": c["high"] * r, "low": c["low"] * r, "close": c["close"] * r, "volume": c["volume"]} for c in p], "XAU"

def gca(a, tf="15m", mn=20):
    if a == "btc": src = [lambda: (bc("BTCUSDT", "15m", 200), "B15"), lambda: (bc("BTCUSDT", "1h", 200), "B1h"), lambda: (cg("bitcoin", 90), "CG")]
    else:
        if tf in ("1h", "4h"): src = [lambda: (td("XAU/USD", "1h", 200), "T1h"), lambda: (bc("PAXGUSDT", "1h", 200), "P1h"), lambda: gc()]
        else: src = [lambda: (td("XAU/USD", "15min",
