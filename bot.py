import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# Import fungsi yang BETUL dari helpers.py
# Perhatikan: generate_signal ditukar kepada generate_smart_signal
from helpers import (
    analyze_gold_btc, 
    get_btc_price, 
    get_gold_price, 
    generate_smart_signal
)

# Load environment variables
load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    logging.critical("TELEGRAM_BOT_TOKEN tidak dijumpai! Sila set di Railway Dashboard.")
    exit(1)

def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🟢 Signal BTC (Buy/Sell)", callback_data='sig_btc'),
            InlineKeyboardButton("🏆 Signal GOLD (Buy/Sell)", callback_data='sig_gold')
        ],
        [
            InlineKeyboardButton("📊 Laporan Penuh (Kedua-dua)", callback_data='full_report')
        ],
        [
            InlineKeyboardButton("🔄 Refresh Harga", callback_data='refresh')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🤖 *Bot Signal PRO: Smart Zones*\n\n"
        "Analisis pintar dengan zon entry adaptif mengikut trend.\n\n"
        "Pilih menu di bawah:"
    )
    await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=get_main_menu())

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pilih signal yang diingini:", reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'sig_btc':
        await query.edit_message_text("🔄 Mengira zon pintar BTC...")
        price = get_btc_price()
        # Panggil fungsi yang betul
        msg = generate_smart_signal("BTC", price) if price else "❌ Gagal ambil data BTC."
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=query.message.chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'sig_gold':
        await query.edit_message_text("🔄 Mengira zon pintar GOLD...")
        price = get_gold_price()
        # Panggil fungsi yang betul
        msg = generate_smart_signal("GOLD", price) if price else "❌ Gagal ambil data GOLD."
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=query.message.chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'full_report':
        await query.edit_message_text("🔄 Analisis penuh sedang dijalankan...")
        msg = analyze_gold_btc()
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=query.message.chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'refresh':
        await query.edit_message_text("🔄 Harga dikemaskini...")
        msg = analyze_gold_btc()
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=query.message.chat_id, text="Menu:", reply_markup=get_main_menu())

def main():
    logging.info("Bot Signal PRO sedang berjalan...")
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
