import os, logging, requests, json, asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
HISTORY_FILE = "/tmp/history.json"

# --- Fungsi Ringkas ---

def gmo():  # gold_market_open
    now = datetime.now(MY_TZ)
    wd, mins = now.weekday(), now.hour * 60 + now.minute
    if wd == 5: return False, "WEEKEND"
    if wd == 6 and mins < 360: return False, "WEEKEND"
    if 300 <= mins < 360: return False, "BREAK"
    return True, "OPEN"

def gs():  # get_session
    h = datetime.now(MY_TZ).hour
    if 15 <= h < 24: return "NY"
    if 8 <= h < 17: return "LDN"
    if 2 <= h < 11: return "TKY"
    return "SYD"

def sh(asset, direction, price, score):  # save_history
    try:
        data = json.load(open(HISTORY_FILE)) if os.path.exists(HISTORY_FILE) else []
        data.append({"time": datetime.now(MY_TZ).strftime("%d/%m %H:%M"), "asset": asset, "direction": direction, "price": price, "score": score})
        json.dump(data[-50:], open(HISTORY_FILE, "w"))
    except Exception: pass

def stats(asset):
    try:
        if not os.path.exists(HISTORY_FILE): return None
        d = [x for x in json.load(open(HISTORY_FILE)) if x.get("asset") == asset]
        if not d: return None
        return {"total": len(d), "buy": sum(1 for x in d if x.get("direction") == "BUY"), "sell": sum(1 for x in d if x.get("direction") == "SELL"), "wait": sum(1 for x in d if x.get("direction") == "WAIT")}
    except: return None

def bc(symbol, interval="15m", limit=200):  # binance_candles
    try:
        r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=5)
        if r.status_code != 200: return []
        return [{"time": x[0], "open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[7])} for x in r.json()]
    except: return []

def gca(asset, tf="15m", minimum=20):  # get_candles
    if asset == "btc":
        sources = [lambda: (bc("BTCUSDT", "15m", 200), "B15"), lambda: (bc("BTCUSDT", "1h", 200), "B1h"), lambda: []]
    else:
        sources = [lambda: (bc("PAXGUSDT", "15m", 200), "P15"), lambda: []]
    for fn in sources:
        try:
            result = fn()
            candles, src = result if isinstance(result, tuple) else (result, "unknown")
            if candles and len(candles) >= minimum: return candles, src
        except: pass
    return [], None

def ggp():  # get_gold_price
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=5)
        if r.status_code == 200: return float(r.json().get("price")), "metals"
    except: pass
    return None, None

def fmt(asset, d):
    if not d: return "Data tidak cukup."
    if not d.get("market_open"): return "Market TUTUP: " + d.get("market_reason", "")
    return f"📊 {asset.upper()}\n💰 Harga: {d.get('price', 0)}\n🎯 Bias: {d.get('bias', 'NEUTRAL')}\n📈 Score: {d.get('score', 0)}/100"

def analyze(asset):
    if asset == "gold":
        opened, reason = gmo()
        if not opened: return {"market_open": False, "market_reason": reason}
    c15, s15 = gca(asset, "15m", 20)
    if len(c15) < 20: return None
    price = c15[-1]["close"] if c15 else 0
    return {
        "market_open": True,
        "price": price,
        "direction": "WAIT",
        "bias": "NEUTRAL",
        "score": 0,
        "source": s15,
        "session": gs()
    }

# --- Bot Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Selamat datang! /gold - Analisis XAU/USD")

async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis GOLD...")
    try:
        d = analyze("gold")
        await update.message.reply_text(fmt("gold", d))
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("Ralat analisis.")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = stats("gold")
    msg = f"📊 Statistik GOLD: BUY {s.get('buy', 0)}, SELL {s.get('sell', 0)}, WAIT {s.get('wait', 0)}" if s else "Tiada data"
    await update.message.reply_text(msg)

# --- Main Function ---

async def main():
    if not TOKEN:
        logger.error("BOT_TOKEN tidak dijumpai!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    logger.info("Bot dimulakan...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

# --- Run Bot ---

if __name__ == "__main__":
    asyncio.run(main())
