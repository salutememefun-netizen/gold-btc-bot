import os
import requests
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# TELEGRAM TOKEN
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")


# ============================================================
# GOLD PRICE
# ============================================================

def get_gold_price():
    try:
        response = requests.get(
            "https://api.gold-api.com/price/XAU",
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        price = float(data["price"])

        return price

    except Exception as e:
        logger.error(f"Gold price error: {e}")
        return None


# ============================================================
# BTC PRICE
# ============================================================

def get_btc_price():
    try:
        response = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        price = float(data["data"]["amount"])

        return price

    except Exception as e:
        logger.error(f"BTC price error: {e}")
        return None


# ============================================================
# SIGNAL
# ============================================================

def make_signal(price, name):

    if price is None:
        return (
            f"❌ Tidak dapat mengambil harga {name} sekarang.\n"
            f"Sila cuba semula."
        )

    entry_low = price * 0.997
    entry_high = price * 1.003

    sl = price * 0.990

    tp1 = price * 1.010
    tp2 = price * 1.018

    return (
        f"📊 *{name} SIGNAL*\n\n"

        f"💰 Harga: `${price:,.2f}`\n\n"

        f"🟢 *Entry Zone*\n"
        f"`{entry_low:,.2f} – {entry_high:,.2f}`\n\n"

        f"🔴 *Stop Loss*\n"
        f"`{sl:,.2f}`\n\n"

        f"🎯 *TP1*\n"
        f"`{tp1:,.2f}`\n\n"

        f"🎯 *TP2*\n"
        f"`{tp2:,.2f}`\n\n"

        f"⚠️ Zone ini masih signal asas.\n"
        f"_Bukan nasihat kewangan._"
    )


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🤖 *GOLD & BTC SIGNAL BOT V2*\n\n"

        "📌 Command:\n\n"

        "/price\n"
        "➡️ Harga Gold & BTC\n\n"

        "/signal gold\n"
        "➡️ Signal Gold\n\n"

        "/signal btc\n"
        "➡️ Signal BTC\n\n"

        "/news\n"
        "➡️ News ringkas\n\n"

        "🚀 Bot aktif."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /PRICE
# ============================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    gold = get_gold_price()
    btc = get_btc_price()

    text = "📈 *HARGA SEMASA*\n\n"

    if gold is not None:
        text += (
            f"🥇 *Gold XAUUSD*\n"
            f"`${gold:,.2f}`\n\n"
        )
    else:
        text += "🥇 Gold: ❌ Data gagal\n\n"

    if btc is not None:
        text += (
            f"₿ *Bitcoin BTC*\n"
            f"`${btc:,.2f}`\n"
        )
    else:
        text += "₿ BTC: ❌ Data gagal\n"

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /SIGNAL
# ============================================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "❌ Sila pilih asset.\n\n"
            "Contoh:\n"
            "/signal gold\n"
            "/signal btc"
        )

        return

    pair = context.args[0].lower()

    if pair == "gold":

        current_price = get_gold_price()

        message = make_signal(
            current_price,
            "GOLD (XAUUSD)"
        )

    elif pair == "btc":

        current_price = get_btc_price()

        message = make_signal(
            current_price,
            "BTC"
        )

    else:

        message = (
            "❌ Asset tidak disokong.\n\n"

            "Asset yang tersedia:\n"
            "🥇 `/signal gold`\n"
            "₿ `/signal btc`"
        )

    await update.message.reply_text(
        message,
        parse_mode="Markdown"
    )


# ============================================================
# /NEWS
# ============================================================

async def news(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "📰 *NEWS MONITOR*\n\n"

        "🥇 *Gold*\n"
        "• USD Index\n"
        "• Federal Reserve\n"
        "• US CPI\n"
        "• NFP\n"
        "• Interest rate\n\n"

        "₿ *Bitcoin*\n"
        "• ETF flow\n"
        "• Funding rate\n"
        "• BTC dominance\n"
        "• US macro data\n\n"

        "⚠️ News auto belum diaktifkan."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram error:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("==========================================")
    print("🤖 GOLD & BTC TELEGRAM BOT V2")
    print("==========================================")

    # --------------------------------------------------------
    # CHECK TOKEN
    # --------------------------------------------------------

    if not TOKEN:

        print("❌ BOT_TOKEN TIDAK DIJUMPAI!")
        print("")
        print("Railway Variables mesti ada:")
        print("")
        print("Name  : BOT_TOKEN")
        print("Value : TOKEN TELEGRAM DARIPADA BOTFATHER")
        print("")

        return

    print("✅ BOT_TOKEN berjaya dibaca!")
    print("🤖 Bot sedang dimulakan...")

    try:

        # ----------------------------------------------------
        # CREATE APPLICATION
        # ----------------------------------------------------

        application = (
            Application
            .builder()
            .token(TOKEN)
            .build()
        )

        # ----------------------------------------------------
        # COMMANDS
        # ----------------------------------------------------

        application.add_handler(
            CommandHandler("start", start)
        )

        application.add_handler(
            CommandHandler("price", price)
        )

        application.add_handler(
            CommandHandler("signal", signal)
        )

        application.add_handler(
            CommandHandler("news", news)
        )

        # ----------------------------------------------------
        # ERROR HANDLER
        # ----------------------------------------------------

        application.add_error_handler(
            error_handler
        )

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        print("🚀 Bot sedang berjalan!")
        print("📡 Telegram polling aktif!")
        print("==========================================")

        application.run_polling(
            drop_pending_updates=True
        )

    except Exception as e:

        print("")
        print("❌ BOT ERROR")
        print(str(e))
        print("")

        logger.exception(
            "Fatal bot error"
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
