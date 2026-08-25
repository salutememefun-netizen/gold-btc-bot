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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    msg = "🤖 Selamat datang, " + user + "!\n\n"
    msg += "Bot Trading GOLD/BTC AI Analysis\n\n"
    msg += "📋 Perintah:\n"
    msg += "/subscribe - Sinyal setiap 1 jam\n"
    msg += "/unsubscribe - Berhenti\n"
    msg += "/test - Test alert\n"
    msg += "/status - Status\n"
    msg += "/price - Harga real-time\n"
    msg += "/help - Bantuan"
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📖 BANTUAN\n\n"
    msg += "/start - Menu utama\n"
    msg += "/subscribe - Subscribe sinyal\n"
    msg += "/unsubscribe - Batalkan subscription\n"
    msg += "/test - Test alert sekarang\n"
    msg += "/status - Cek status subscription\n"
    msg += "/price - Harga real-time BTC & GOLD\n"
    msg += "/help - Bantuan ini\n\n"
    msg += "Indikator: RSI, MACD, Bollinger Bands\n"
    msg += "Signal: BUY / SELL / WAIT\n\n"
    msg += "Disclaimer: Bukan financial advice!"
    await update.message.reply_text(msg)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if add_subscriber_db(chat_id):
        msg = "Berhasil Subscribe!\n"
        msg += "Anda akan terima sinyal setiap 1 jam.\n"
        msg += "Ketik /test untuk cuba sekarang."
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Gagal subscribe. Cuba lagi.")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if remove_subscriber_db(chat_id):
        msg = "Unsubscribe Berjaya!\n"
        msg += "Anda tidak akan terima sinyal lagi."
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Anda belum subscribe.")

async def test_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Loading... Ambil data pasar...")
    try:
        btc = get_btc_price()
        gold = get_gold_price()
        if not btc or not gold:
            await update.message.reply_text("Gagal ambil data. Cuba lagi.")
            return
        msg = "TEST ALERT\n\n"
        msg += generate_ultimate_signal("BTC", btc)
        msg += "\n\n============================\n\n"
        msg += generate_ultimate_signal("GOLD", gold)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text("Error: " + str(e))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = get_all_subscribers()
    if chat_id in subs:
        msg = "Status: SUBSCRIBED\n"
        msg += "Anda terima sinyal setiap jam.\n"
    else:
        msg = "Status: TIDAK SUBSCRIBED\n"
        msg += "Ketik /subscribe untuk mula.\n"
    msg += "\nTotal Subscriber: " + str(len(subs))
    await update.message.reply_text(msg)

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Loading... Ambil harga terkini...")
    try:
        btc = get_btc_price()
        gold = get_gold_price()
        if btc and gold:
            msg = "HARGA REAL-TIME\n\n"
            msg += "BTC  : $" + "{:,.2f}".format(btc) + "\n"
            msg += "GOLD : $" + "{:,.2f}".format(gold) + "\n\n"
            msg += "Update: Sekarang"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("Gagal ambil data harga.")
    except Exception as e:
        await update.message.reply_text("Error: " + str(e))

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error: " + str(context.error))

def main():
    logger.info("Starting Bot...")
    if not init_db():
        logger.error("Gagal init DB")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("test", test_alert))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("price", price))
    app.add_error_handler(error_handler)

    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
