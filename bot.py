#!/usr/bin/env python3
"""
Main Bot Telegram untuk Trading GOLD/BTC
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Import dari helpers
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

# ============================================
# TOKEN & CONFIG (HARD CODED)
# ============================================
# Gantikan dengan token dari @BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" 

if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    logger.error("❌ Sila masukkan BOT_TOKEN yang betul di dalam kod!")
    exit(1)

# ============================================
# HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"🤖 *Selamat datang, {user.first_name}!*\\n\\n"
        "Bot Trading GOLD/BTC AI Analysis\\n\\n"
        "*📋 Perintah:*\\n"
        "/subscribe - Sinyal setiap 1 jam\\n"
        "/unsubscribe - Berhenti\\n"
        "/test - Test alert\\n"
        "/status - Status\\n"
        "/price - Harga real-time"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if add_subscriber_db(chat_id):
        await update.message.reply_text("✅ *Berhasil Subscribe!*\\nAnda akan terima sinyal setiap 1 jam.", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Gagal subscribe.", parse_mode='Markdown')

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if remove_subscriber_db(chat_id):
        await update.message.reply_text("✅ *Unsubscribe Berhasil*\\nAnda tidak akan terima sinyal lagi.", parse_mode='Markdown')
    else:
        await update.message.reply_text("ℹ️ Anda belum subscribe.", parse_mode='Markdown')

async def test_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 *Loading...*")
    try:
        btc = get_btc_price()
        gold = get_gold_price()
        if not btc or not gold:
            await update.message.reply_text("❌ Gagal ambil data.")
            return
        msg = (
            f"🧪 *TEST ALERT*\\n\\n"
            f"{generate_ultimate_signal('BTC', btc)}\\n\\n"
            "══════════════════════════════\\n\\n"
            f"{generate_ultimate_signal('GOLD', gold)}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = get_all_subscribers()
    if chat_id in subs:
        msg = "✅ *SUBSCRIBED*\\nAnda terima sinyal setiap jam."
    else:
        msg = "❌ *NOT SUBSCRIBED*\\nKetik /subscribe untuk mula."
    msg += f"\\n\\n📊 Total: {len(subs)}"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 *Loading...*")
    try:
        btc = get_btc_price()
        gold = get_gold_price()
        if btc and gold:
            msg = f"💰 *HARGA REAL-TIME*\\n\\n🔵 BTC: \\${btc:,.2f}\\n🟡 GOLD: \\${gold:,.2f}"
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Gagal ambil data.", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    logger.info("🚀 Starting Bot...")
    if not init_db():
        logger.error("❌ Gagal init DB")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("test", test_alert))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("price", price))
    app.add_error_handler(error_handler)
    
    logger.info("✅ Bot started. Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
