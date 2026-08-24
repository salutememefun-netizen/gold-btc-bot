import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
from scheduler import setup_scheduler, add_subscriber, remove_subscriber
from helpers import analyze_gold_btc, get_btc_price, get_gold_price, generate_smart_signal

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
        ],
        [
            InlineKeyboardButton("🔔 Subscribe Auto-Alert", callback_data='sub_alert'),
            InlineKeyboardButton("🔕 Unsubscribe Alert", callback_data='unsub_alert')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🤖 *Bot Signal PRO: Smart Zones*\n\n"
        "Analisis pintar dengan zon entry adaptif, RSI, & EMA.\n\n"
        "Perintah:\n"
        "/subscribe - Terima alert automatik setiap 1 jam\n"
        "/unsubscribe - Hentikan alert\n\n"
        "Pilih menu di bawah:"
    )
    await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=get_main_menu())

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pilih signal yang diingini:", reply_markup=get_main_menu())

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_subscriber(chat_id)
    await update.message.reply_text(
        "✅ *Berjaya Disubscribe!*\n"
        "Anda akan menerima laporan pasaran automatik setiap 1 jam.",
        parse_mode='Markdown'
    )

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    remove_subscriber(chat_id)
    await update.message.reply_text(
        "❌ *Berjaya Dihentikan!*\n"
        "Anda tidak akan menerima alert automatik lagi.",
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'sig_btc':
        await query.edit_message_text("🔄 Mengira zon pintar BTC...")
        price = get_btc_price()
        msg = generate_smart_signal("BTC", price) if price else "❌ Gagal ambil data BTC."
        await query.edit_message_text(msg, parse_mode='Markdown')
        await context.bot.send_message(chat_id=query.message.chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'sig_gold':
        await query.edit_message_text("🔄 Mengira zon pintar GOLD...")
        price = get_gold_price()
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

    elif query.data == 'sub_alert':
        chat_id = query.message.chat_id
        add_subscriber(chat_id)
        await query.edit_message_text(
            "✅ *Disubscribe!*\nAnda akan terima alert setiap 1 jam.",
            parse_mode='Markdown'
        )
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

    elif query.data == 'unsub_alert':
        chat_id = query.message.chat_id
        remove_subscriber(chat_id)
        await query.edit_message_text(
            "❌ *Unsubscribe!*\nAlert telah dihentikan.",
            parse_mode='Markdown'
        )
        await context.bot.send_message(chat_id=chat_id, text="Menu:", reply_markup=get_main_menu())

def main():
    logging.info("Bot Signal PRO sedang berjalan...")
    application = Application.builder().token(TOKEN).build()

    # Daftar handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Mula Scheduler (Auto-Alert)
    setup_scheduler(application)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
