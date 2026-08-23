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
        return f"❌ Gagal ambil harga {name}"

    entry_low = price * 0.997
    entry_high = price * 1.003
    sl = price * 0.990
    tp1 = price * 1.010
    tp2 = price * 1.018

    return (
        f"📊 *{name} SIGNAL*\n\n"
        f"💰 Harga sekarang: `${price:,.2f}`\n\n"
        f"🟢 Entry Zone: `\( {entry_low:,.2f}` – ` \){entry_high:,.2f}`\n"
        f"🔴 Stop Loss: `${sl:,.2f}`\n"
        f"🎯 TP1: `${tp1:,.2f}`\n"
        f"🎯 TP2: `${tp2:,.2f}`\n\n"
        f"_Nota: Zone kasar. Bukan nasihat kewangan._"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Gold & BTC Signal Bot*\n\n"
        "Command:\n"
        "/price – Harga semasa\n"
        "/signal gold – Signal Gold\n"
        "/signal btc – Signal BTC\n"
        "/news – News ringkas\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gold = get_gold_price()
    btc = get_btc_price()

    text = "📈 *Harga Semasa*\n\n"
    if gold:
        text += f"🥇 Gold (XAUUSD): `${gold:,.2f}`\n"
    else:
        text += "🥇 Gold: Gagal ambil data\n"
    if btc:
        text += f"₿ BTC: `${btc:,.2f}`\n"
    else:
        text += "₿ BTC: Gagal ambil data\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Contoh:\n/signal gold\n/signal btc")
        return

    pair = context.args[0].lower()

    if pair == "gold":
        price = get_gold_price()
        msg = make_signal(price, "GOLD (XAUUSD)")
    elif pair == "btc":
        price = get_btc_price()
        msg = make_signal(price, "BTC")
    else:
        msg = "Hanya support: gold atau btc"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📰 *News Ringkas*\n\n"
        "• Gold: Pantau USD Index & Fed speech\n"
        "• BTC: Pantau ETF flow & funding rate\n\n"
        "_Versi news auto akan ditambah kemudian._"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    if not TOKEN:
        print("BOT_TOKEN tidak dijumpai!")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("news", news))

    print("Bot sedang berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
