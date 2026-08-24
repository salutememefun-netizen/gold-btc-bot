import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Import fungsi dari helpers.py
# Nota: Kita guna analyze_gold_btc sebagai fungsi utama
from helpers import analyze_gold_btc

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Dapatkan token dari Railway Environment Variable
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    logging.critical("TELEGRAM_BOT_TOKEN tidak dijumpai! Sila set di Railway Dashboard.")
    exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesej alu-aluan bila user tekan /start"""
    welcome_text = (
        "🤖 *Selamat Datang ke Bot Analisis GOLD & BTC!*\n\n"
        "Saya boleh berikan harga semasa dan analisis ringkas.\n\n"
        "Perintah tersedia:\n"
        "/analyze - Semak harga BTC & GOLD terkini\n"
        "/start - Mesej alu-aluan ini\n\n"
        "Ketik /analyze untuk bermula! 🚀"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menjalankan analisis pasar"""
    await update.message.reply_text("🔄 Sedang menganalisis pasaran... Tunggu sekejap.")
    
    try:
        # Panggil fungsi dari helpers.py
        laporan = analyze_gold_btc()
        await update.message.reply_text(laporan, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Ralat semasa analisis: {e}")
        await update.message.reply_text("❌ Maaf, berlaku ralat semasa mendapatkan data pasaran. Sila cuba lagi nanti.")

def main():
    """Mula menjalankan bot"""
    logging.info("Bot sedang dimulakan...")
    
    # Bina aplikasi
    application = Application.builder().token(TOKEN).build()
    
    # Daftar handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_command))
    
    # Mula polling
    logging.info("Bot sedang mendengar...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
