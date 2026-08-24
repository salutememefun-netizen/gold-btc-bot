import os, logging, requests, asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Selamat datang!\n\n/gold - Harga GOLD\n/btc - Harga BTC")

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=5)
        p = float(r.json()["price"])
        await update.message.reply_text(f"💰 GOLD: ${p:.2f} USD")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Gagal dapat harga GOLD")

async def btc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        p = float(r.json()["price"])
        await update.message.reply_text(f"💰 BTC: ${p:.2f} USD")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Gagal dapat harga BTC")

async def main():
    if not TOKEN:
        logger.error("BOT_TOKEN tiada!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add
