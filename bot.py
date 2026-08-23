import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# TELEGRAM BOT TOKEN
# Ambil token daripada Environment Variable BOT_TOKEN
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")


# ============================================================
# HARGA GOLD
# ============================================================

def get_gold_price():
    try:
        r = requests.get(
            "https://api.gold-api.com/price/XAU",
            timeout=10
        )
        r.raise_for_status()

        data = r.json()
        return float(data["price"])

    except Exception as e:
        print(f"Gold price error: {e}")
        return None


# ============================================================
# HARGA BTC
# ============================================================

def get_btc_price():
    try:
        r = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            timeout=10
        )
        r.raise_for_status()

        data = r.json()
        return float(data["data"]["amount"])

    except Exception as e:
        print(f"BTC price error: {e}")
        return None


# ============================================================
# SIGNAL SIMPLE
# ============================================================

def make_signal(price, name):

    if price is None:
        return f"❌ Gagal ambil harga {name}"

    # Zone kasar
    entry_low = price * 0.997
    entry_high = price * 1.003

    sl = price * 0.990

    tp1 = price * 1.010
    tp2 = price * 1.018

    return (
        f"📊 *{name} SIGNAL*\n\n"
        f"💰 Harga sekarang: `${price:,.2f}`\n\n"
        f"🟢 Entry Zone: `({entry_low:,.2f} – {entry_high:,.2f})`\n"
        f"🔴 Stop Loss: `${sl:,.2f}`\n"
        f"🎯 TP1: `${tp1:,.2f}`\n"
        f"🎯 TP2: `${tp2:,.2f}`\n\n"
        f"_Nota: Ini zone kasar (0.3%–1.8%). "
        f"Bukan nasihat kewangan._"
    )


# ============================================================
# /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "🤖 *Gold & BTC Signal Bot*\n\n"
        "Command:\n"
        "/price – Harga semasa\n"
        "/signal gold – Signal Gold\n"
        "/signal btc – Signal BTC\n"
        "/news – News ringkas\n"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /PRICE
# ============================================================

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):

    gold = get_gold_price()
    btc = get_btc_price()

    text = "📈 *Harga Semasa*\n\n"

    if gold is not None:
        text += f"🥇 Gold (XAUUSD): `${gold:,.2f}`\n"
    else:
        text += "🥇 Gold: Gagal ambil data\n"

    if btc is not None:
        text += f"₿ BTC: `${btc:,.2f}`\n"
    else:
        text += "₿ BTC: Gagal ambil data\n"

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /SIGNAL
# ============================================================

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "Contoh:\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    pair = context.args[0].lower()

    if pair == "gold":

        price = get_gold_price()

        msg = make_signal(
            price,
            "GOLD (XAUUSD)"
        )

    elif pair == "btc":

        price = get_btc_price()

        msg = make_signal(
            price,
            "BTC"
        )

    else:

        msg = (
            "❌ Pair tidak disokong.\n\n"
            "Hanya support:\n"
            "/signal gold\n"
            "/signal btc"
        )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown"
    )


# ============================================================
# /NEWS
# ============================================================

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "📰 *News Ringkas*\n\n"
        "• Gold: Pantau USD Index & Fed speech\n"
        "• BTC: Pantau ETF flow & funding rate\n\n"
        "_Versi news auto akan ditambah kemudian._"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # Check BOT_TOKEN
    if not TOKEN:

        print("❌ BOT_TOKEN tidak dijumpai!")
        print("")
        print("Pastikan Environment Variable dibuat:")
        print("Variable Name : BOT_TOKEN")
        print("Value         : Token Telegram daripada BotFather")
        print("")
        print("⚠️ Jangan letakkan token Telegram dalam kod GitHub.")

        return

    print("✅ BOT_TOKEN berjaya dibaca!")
    print("🤖 Bot sedang dimulakan...")

    try:

        app = (
            Application
            .builder()
            .token(TOKEN)
            .build()
        )

        # Commands
        app.add_handler(
            CommandHandler("start", start)
        )

        app.add_handler(
            CommandHandler("price", price)
        )

        app.add_handler(
            CommandHandler("signal", signal)
        )

        app.add_handler(
            CommandHandler("news", news)
        )

        print("🚀 Bot sedang berjalan!")
        print("📡 Telegram polling aktif...")

        app.run_polling()

    except Exception as e:

        print(f"❌ BOT ERROR: {e}")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
