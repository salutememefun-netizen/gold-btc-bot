import os, logging, requests, asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, _): 
    await update.message.reply_text("Bot siap. Gunakan /gold atau /btc")

async def gold(update: Update, _):
    try:
        p = requests.get("https://api.metals.live/v1/spot/gold", timeout=5).json()["price"]
        await update.message.reply_text(f"💰 GOLD: ${float(p):.2f}")
    except: 
        await update.message.reply_text("❌ Gagal dapat harga")

async def btc(update: Update, _):
    try:
        p = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5).json()["price"]
        await update.message.reply_text(f"💰 BTC: ${float(p):.2f}")
    except: 
        await update.message.reply_text("❌ Gagal dapat harga")

async def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("btc", btc))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
