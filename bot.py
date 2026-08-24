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

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Linux; Android 13) Chrome/120"})

auto_chats = set()
last_signals = {}

# Import fungsi-fungsi dari helpers.py
from helpers import (
    gold_market_open, get_session, save_history, get_stats,
    binance_candles, coingecko_ohlc, twelvedata_candles,
    get_gold_price, gold_candles, get_candles, get_live_price,
    get_news, check_news_risk, ema, rsi_calc, atr_calc, adx_calc,
    rsi_divergence, get_swings, structure, candle_conf,
    liq_sweep, bos_detect, retest_detect, calc_bias, build_zone,
    trend, analyze
)

def fmt(asset, d):
    if not d: return "Data tidak cukup untuk analisis."
    if not d.get("market_open"): return "Market TUTUP: " + d.get("market_reason", "")

    name = "GOLD (XAU/USD)" if asset == "gold" else "BITCOIN (BTC/USD)"
    direction = d["direction"]
    price = d["price"]
    score = d["score"]
    confidence = d["confidence"]

    if direction == "BUY": signal_line = "🟢 SIGNAL: BUY"
    elif direction == "SELL": signal_line = "🔴 SIGNAL: SELL"
    else: signal_line = "⏳ SIGNAL: TUNGGU"

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 " + name,
        "━━━━━━━━━━━━━━━━━━━━",
        signal_line,
        "💰 Harga: " + str(round(price, 2)),
        "🎯 Bias: " + d["bias"],
        "📈 Score: " + str(score) + "/100",
        "🔒 Confidence: " + str(confidence) + "%",
        "🕐 Session: " + d.get("session", ""),
        "📡 Source: " + str(d.get("source", "")),
        "",
    ]

    if d.get("rsi") is not None: lines.append("RSI: " + str(round(d["rsi"], 1)))
    if d.get("adx") is not None: lines.append("ADX: " + str(round(d["adx"], 1)))
    if d.get("atr") is not None: lines.append("ATR: " + str(round(d["atr"], 2)))
    if d.get("divergence") and d["divergence"] != "NONE": lines.append("DIV: " + d["divergence"])

    lines.append("")
    lines.append("📋 Sebab:")
    for r in d.get("reasons", []): lines.append("  • " + r)

    if d.get("missing"):
        lines.append("")
        lines.append("⏳ Tunggu:")
        for m in d["missing"]: lines.append("  • " + m)

    if direction in ("BUY", "SELL"):
        lines.append("")
        lines.append("🎯 Level:")
        if d.get("sl") is not None: lines.append("  SL : " + str(round(d["sl"], 2)))
        if d.get("tp1") is not None: lines.append("  TP1: " + str(round(d["tp1"], 2)) + " (RR " + str(d.get("rr1", "")) + ")")
        if d.get("tp2") is not None: lines.append("  TP2: " + str(round(d["tp2"], 2)) + " (RR " + str(d.get("rr2", "")) + ")")
        if d.get("zone_low") is not None: lines.append("  Zone: " + str(round(d["zone_low"], 2)) + " - " + str(round(d["zone_high"], 2)))

    if d.get("news"):
        lines.append("")
        lines.append("📰 News USD minggu ini:")
        for n in d["news"][:3]: lines.append("  • " + n.get("title", ""))

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "👋 Selamat datang!\n\n/gold - Analisis XAU/USD\n/btc - Analisis BTC/USD\n/auto - Auto Alert ON\n/stop - Auto Alert OFF\n/stats - Statistik"
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/gold, /btc, /auto, /stop, /stats, /start")

async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis GOLD...")
    try:
        d = analyze("gold")
        await update.message.reply_text(fmt("gold", d))
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("Ralat analisis.")

async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis BTC...")
    try:
        d = analyze("btc")
        await update.message.reply_text(fmt("btc", d))
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("Ralat analisis.")

async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auto_chats.add(update.effective_chat.id)
    await update.message.reply_text("✅ Auto Alert AKTIF (setiap 5 minit).")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auto_chats.discard(update.effective_chat.id)
    await update.message.reply_text("🛑 Auto Alert DIMATIKAN.")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📊 Statistik\n"]
    for asset in ("gold", "btc"):
        s = get_stats(asset)
        name = "GOLD" if asset == "gold" else "BTC"
        if s:
            lines.append(f"{name}: BUY {s['buy']}, SELL {s['sell']}, WAIT {s['wait']}")
        else:
            lines.append(f"{name}: Tiada data")
    await update.message.reply_text("\n".join(lines))

async def auto_poll():
    while True:
        await asyncio.sleep(300) # 5 minit
        for chat_id in list(auto_chats):
            try:
                for asset in ["gold", "btc"]:
                    d = analyze(asset)
                    if d and d.get("market_open"):
                        prev = last_signals.get((chat_id, asset), "WAIT")
                        curr = d["direction"]
                        if prev != curr and curr != "WAIT":
                            msg = f"🚨 ALERT {asset.upper()}: {curr}\n"
                            msg += f"💰 {d['price']}\n🎯 {d['bias']}\n📈 Score: {d['score']}"
                            try:
                                await context.bot.send_message(chat_id=chat_id, text=msg)
                                last_signals[(chat_id, asset)] = curr
                            except Exception as e:
                                logger.error(f"Send msg error: {e}")
            except Exception as e:
                logger.error(f"Poll error: {e}")

async def main():
    if not TOKEN:
        logger.error("No BOT_TOKEN")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("gold", gold_cmd))
    app.add_handler(CommandHandler("btc", btc_cmd))
    app.add_handler(CommandHandler("auto", auto_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    
    asyncio.create_task(auto_poll())
    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
