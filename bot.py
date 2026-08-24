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
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 13) Chrome/120"})

auto_chats = set()
last_signals = {}

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
            with open(HISTORY_FILE) as f: data = json.load(f)
        data.append({"time": datetime.now(MY_TZ).strftime("%d/%m %H:%M"), "asset": asset, "direction": direction, "price": price, "score": score})
        with open(HISTORY_FILE, "w") as f: json.dump(data[-50:], f)
    except Exception as e: logger.warning("history error: %s", e)

def get_stats(asset):
    try:
        if not os.path.exists(HISTORY_FILE): return None
        with open(HISTORY_FILE) as f: data = json.load(f)
        d = [x for x in data if x.get("asset") == asset]
        if not d: return None
        return {"total": len(d), "buy": sum(1 for x in d if x.get("direction") == "BUY"), "sell": sum(1 for x in d if x.get("direction") == "SELL"), "wait": sum(1 for x in d if x.get("direction") == "WAIT")}
    except Exception: return None

def binance_candles(symbol, interval="15m", limit=200):
    try:
        r = SESSION.get("https://api.binance.com/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
        if r.status_code != 200: return []
        out = []
        for x in r.json():
            try: out.append({"time": x[0], "open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[7])})
            except: pass
        return out
    except Exception as e: logger.warning("binance %s: %s", symbol, e); return []

def coinge
