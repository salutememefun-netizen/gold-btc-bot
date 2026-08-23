
import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

def get_gold_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
        data = r.json()
        return float(data["price"])
    except:
        return None

def get_btc_price():
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
        data = r.json()
        return float(data["data"]["amount"])
    except:
        return None

def make_signal(price, name):
    if price is None:
        return f"Gagal ambil harga {name}"

    entry_low = round(price * 0.997, 2)
    entry_high = round(price * 1.003, 2)
    sl = round(price * 0.990, 2)
    tp1 = round(price * 1.010, 2)
    tp2 = round(price * 1.018, 2)

    text = f"📊 {name} SIGNAL\n\n"
    text += f"Harga sekarang: {price}\n\n"
    text += f"Entry Zone: {entry_low} - {entry_high}\n"
    text += f"Stop Loss: {sl}\n"
    text += f"TP1: {tp1}\n"
    text += f"TP2: {tp2}\n\n"
    text += "Nota: Zone kasar. Bukan nasihat kewangan."
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Gold & BTC Signal Bot\n\n"
    text += "/price - Harga semasa\n"
    text += "/signal gold - Signal Gold\n"
    text += "/signal btc - Signal BTC\n"
    text += "/news - News ringkas"
    await update.message.reply_text(text)

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gold = get_gold_price()
    btc = get_btc_price()

    text = "Harga Semasa\n\n"
    if gold:
        text += f"Gold (XAUUSD): {gold}\n"
    else:
        text += "Gold: Gagal ambil data\n"
    if btc:
        text += f"BTC: {btc}\n"
    else:
        text += "BTC: Gagal ambil data\n"

    await update.message.reply_text(text)

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Contoh:\n/signal gold\n/signal btc")
        return

    pair = context.args[0].lower()

    if pair == "gold":
        p = get_gold_price()
        msg = make_signal(p, "GOLD")
    elif pair == "btc":
        p = get_btc_price()
        msg = make_signal(p, "BTC")
    else:
        msg = "Hanya support: gold atau btc"

    await update.message.reply_text(msg)

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "News Ringkas\n\n"
    text += "- Gold: Pantau USD Index & Fed speech\n"
    text += "- BTC: Pantau ETF flow & funding rate\n\n"
    text += "Versi news auto akan ditambah kemudian."
    await update.message.reply_text(text)

def main():
    if not TOKEN:
        print("BOT_TOKEN tidak dijumpai!")
        return

    print("Bot sedang berjalan...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("news", news))

    app.run_polling()

if __name__ == "__main__":
    main()
