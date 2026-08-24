import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from helpers import (
    MY_TZ, last_signal_state, load_alert_state,
    save_alert_state, get_stats
)
from analysis import analyze
from datetime import datetime

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
polling_interval = 300
auto_chat_ids = set()


def fmt(asset, d):
    if not d:
        return "Data tidak cukup untuk analisis."
    if not d.get("market_open"):
        return "Market TUTUP: " + d.get("market_reason", "")

    name = "GOLD (XAU/USD)" if asset == "gold" else "BITCOIN (BTC/USD)"
    direction = d["direction"]
    price = d["price"]
    score = d["score"]
    confidence = d["confidence"]

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
        "🎯 Bias: " + d["bias"],
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
            lines.append("  SL : " + str(round(d["sl"], 2)))
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
        "/auto - Auto alert ON (5 minit)\n"
        "/stop - Auto alert OFF\n"
        "/stats - Statistik signal\n"
        "/help - Bantuan"
    )
    await update.message.reply_text(msg)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 Arahan Bot:\n\n"
        "/gold - Signal analisis GOLD\n"
        "/btc - Signal analisis BTC\n"
        "/auto - Hidupkan auto alert\n"
        "/stop - Matikan auto alert\n"
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
        await update.message.reply_text("Ralat semasa analisis. Cuba lagi.")


async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis BTC...")
    try:
        d = analyze("btc")
        await update.message.reply_text(fmt("btc", d))
    except Exception as e:
        logger.error("btc_cmd error: %s", e)
        await update.message.reply_text("Ralat semasa analisis. Cuba lagi.")


async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    auto_chat_ids.add(chat_id)
    await update.message.reply_text(
        "✅ Auto alert AKTIF!\n"
        "Bot akan hantar signal setiap 5 minit jika ada perubahan.\n"
        "Taip /stop untuk hentikan."
    )


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    auto_chat_ids.discard(chat_id)
    await update.message.reply_text("🛑 Auto alert DIMATIKAN.")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📊 Statistik Signal\n"]
    for asset in ("gold", "btc"):
        s = get_stats(asset)
        name = "GOLD" if asset == "gold" else "BTC"
        if s:
            lines.append(name + ":")
            lines.append("  Total : " + str(s["total"]))
            lines.append("  BUY   : " + str(s["buy"]))
            lines.append("  SELL  : " + str(s["sell"]))
            lines.append("  WAIT  : " + str(s["wait"]))
        else:
            lines.append(name + ": Tiada rekod")
