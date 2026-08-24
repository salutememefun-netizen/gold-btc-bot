import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
from helpers import (
    analyze_gold_btc, get_btc_price, get_gold_price, 
    generate_smart_signal, add_subscriber_db, remove_subscriber_db, init_db
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    logging.critical("TELEGRAM_BOT_TOKEN tidak dijumpai!")
    exit(1)

# Initialize database
init_db()

def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🟢 Signal BTC", callback_data='sig_btc'),
            InlineKeyboardButton("🏆 Signal GOLD", callback_data='sig_gold')
        ],
        [
            InlineKeyboardButton("📊 Laporan Penuh", callback_data='full_report')
        ],
        [
            InlineKeyboardButton("🔔 Subscribe Auto-Alert", callback_data='sub_alert'),
            InlineKeyboardButton("🔕 Unsubscribe", callback_data='unsub_alert')
        ],
        [
            InlineKeyboardButton("🧪 Test Alert (Manual)", callback_data='test_alert')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🤖 *Bot Signal PRO: Smart Zones*\n\n"
        "Analisis dengan RSI, EMA & Smart Zones.\n\n"
        "🔔 *Auto-Alert:* Subscribe untuk dapat laporan setiap 1 jam!\n"
        "🧪 *Test Alert:* Tekan butang 'Test Alert' untuk test sekarang."
    )
    await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == 'sig_btc':
        await query.edit_message_text("🔄 Mengira BTC...")
        price = get_btc_price()
        msg = generate_smart_signal("BTC", price) if price else "❌ Gagal."
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'sig_gold':
        await query.edit_message_text("🔄 Mengira GOLD...")
        price = get_gold_price()
        msg = generate_smart_signal("GOLD", price) if price else "❌ Gagal."
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'full_report':
        await query.edit_message_text("🔄 Analisis...")
        msg = analyze_gold_btc()
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'sub_alert':
        if add_subscriber_db(chat_id):
            await query.edit_message_text("✅ *Disubscribe!*\nAlert setiap 1 jam.", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Ralat sambungan DB. Cuba lagi.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'unsub_alert':
        if remove_subscriber_db(chat_id):
            await query.edit_message_text("❌ *Unsubscribe!*\nAlert dihentikan.", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Ralat. Cuba lagi.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'test_alert':
        await query.edit_message_text("🧪 *Test Alert:*\nMenghantar test message...")
        try:
            from alert import send_alerts
            import asyncio
            await send_alerts()  # Panggil fungsi dari alert.py
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ *Test Berjaya!*\nAlert dihantar ke semua subscriber.\nCheck Telegram anda sekarang!",
                parse_mode='Markdown'
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ *Test Gagal:*\n{str(e)}",
                parse_mode='Markdown'
            )
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

def main():
    logging.info("Bot PRO bermula...")
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
