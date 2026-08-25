#!/usr/bin/env python3
"""
Main Bot Telegram untuk Trading GOLD/BTC
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from helpers import (
    init_db,
    add_subscriber_db,
    remove_subscriber_db,
    get_all_subscribers,
    generate_ultimate_signal,
    get_btc_price,
    get_gold_price
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("ERROR: BOT_TOKEN tidak dijumpai!")
    exit(1)

# HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    msg = (
        f"🤖 Selamat datang, {user}!\\n\\n"
        "Bot Trading GOLD/BTC AI Analysis\\n\\n"
        "📋 Perintah:\\n"
        "/subscribe - Sinyal setiap 1 jam\\n"
        "/unsubscribe - Berhenti\\n"
        "/test - Test alert\\n"
        "/status - Status\\n"
        "/price - Harga real-time\\n"
        "/help - Bantuan"
    )
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 BANTUAN\\n\\n"
        "/start - Menu utama\\n"
        "/subscribe - Subscribe sinyal\\n"
        "/unsubscribe - Batalkan subscription\\n"
        "/test - Test alert sekarang\\n"
        "/status - Cek status subscription\\n"
        "/price - Harga real-time BTC & GOLD\\n"
        "/help - Bantuan ini\\n\\n"
        "Indikator: RSI, MACD, Bollinger Bands\\n"
        "Signal: BUY, SELL, WAIT\\n\\n"
        "⚠️ Disclaimer: Bukan financial advice!"
    )
    await update.message.reply_text(msg)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if add_subscriber_db(chat_id):
        await update.message.reply_text("✅ Berhasil Subscribe!\\nAnda akan terima sinyal setiap 1 jam.")
    else:
        await update.message.reply_text("❌ Gagal subscribe.")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if remove_subscriber_db(chat_id):
        await update.message.reply_text("✅ Unsubscribe Berhasil!")
    else:
        await update.message.reply_text("ℹ️ Anda belum subscribe.")

async def test_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading...")
    try:
        btc = get_btc_price()
        gold = get_gold_price()
        if not btc or not gold:
            await update.message.reply_text("❌ Gagal ambil data.")
            return
        msg = (
            "🧪 TEST ALERT\\n\\n"
            f"{generate_ultimate_signal('BTC', btc)}\\n\\n"
            "============================\\n\\n"
            f"{generate_ultimate_signal('GOLD', gold)}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = get_all_subscribers()
    if chat_id in subs:
        msg = "✅ SUBSCRIBED\\nAnda terima sinyal setiap jam."
    else:
        msg = "❌ NOT SUBSCRIBED\\nKetik /subscribe untuk mula."
    msg += f"\\n\\n📊 Total: {len(subs)}"
    await update.message.reply_text(msg)

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading...")
    try:
        btc = get_btc_price()
        gold = get_gold_price()
        if btc and gold:
            msg = f"💰 HARGA REAL-TIME\\n\\n🔵 BTC: ${btc:,.2f}\\n🟡 GOLD: ${gold:,.2f}"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("❌ Gagal ambil data.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    logger.info("🚀 Starting Bot...")
    if not init_db():
        logger.error("❌ Gagal init DB")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("test", test_alert))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("price", price))
    
    app.add_error_handler(error_handler)
    
    logger.info("✅ Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
