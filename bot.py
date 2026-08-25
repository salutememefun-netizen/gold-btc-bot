#!/usr/bin/env python3
"""
Main Bot Telegram - Auto detect variable name
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

# AUTO DETECT NAMA VARIABLE
BOT_TOKEN = (
    os.getenv("BOT_TOKEN") or
    os.getenv("TELEGRAM_BOT_TOKEN") or
    os.getenv("TELEGRAM_BOT_API_TOKEN") or
    os.getenv("TG_BOT_TOKEN")
)

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN tidak dijumpai! Senarai semua variable:")
    for key in os.environ.keys():
        if 'TOKEN' in key.upper() or 'BOT' in key.upper():
            logger.error(f"   {key} = {os.getenv(key)[:10]}...")
    exit(1)

logger.info(f"✅ Guna token dari: {[k for k in os.environ if os.getenv(k) == BOT_TOKEN][0]}")

# HANDLERS (Sama seperti sebelum ini)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = f"🤖 *Selamat datang, {user.first_name}!*\\n\\nBot sedang berjalan!"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if add_subscriber_db(chat_id):
        await update.message.reply_text("✅ Berhasil Subscribe!")
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
        if btc and gold:
            msg = f"💰 BTC: ${btc:,.2f}\\n🟡 GOLD: ${gold:,.2f}"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("❌ Gagal ambil data.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = get_all_subscribers()
    msg = "✅ SUBSCRIBED" if chat_id in subs else "❌ NOT SUBSCRIBED"
    await update.message.reply_text(msg)

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading...")
    btc = get_btc_price()
    gold = get_gold_price()
    if btc and gold:
        msg = f"💰 BTC: ${btc:,.2f}\\n🟡 GOLD: ${gold:,.2f}"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Gagal.")

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
    
    logger.info("✅ Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
