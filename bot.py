import os, logging, requests, json, asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

def get_gold_price():
    try:
        r = requests.get("https://api.metals.live/v1/spot/gold", timeout=5)
        if r.status_code == 200:
            p = r.json().get("price")
            if p: return float(p)
    except Exception as e:
        logger.warning("gold price error: %s", e)
    return None

def get_btc_price():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        if r.status_code == 200:
            return float(r.json().get("price", 0))
    except Exception as e:
        logger.warning("btc price error: %s", e)
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "👋 Selamat datang!\n\n/gold - Harga GOLD\n/btc - Harga BTC"
    await update.message.reply_text(msg)

async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_gold_price()
    if price:
        await update.message.reply_text(f"💰 GOLD: ${price:.2f} USD")
    else:
        await update.message.reply_text("❌ Gagal dapat harga GOLD. Cuba lagi.")

async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = get_btc_price()
    if price:
        await update.message.reply_text(f"💰 BTC: ${price:.2f} USD")
    else:
        await update.message.reply_text("❌ Gagal dapat harga BTC. Cuba lagi.")

async def main():
    if not TOKEN:
        logger.error("BOT_TOKEN tidak dijumpai!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold_cmd))
    app.add_handler(CommandHandler("btc", btc_cmd))
    logger.info("Bot berjalan...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
