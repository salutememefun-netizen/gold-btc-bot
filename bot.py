import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from analyzer import generate_signal, get_price

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Menu Butang Utama ---
def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🟢 Signal BTC", callback_data="signal_btc"),
            InlineKeyboardButton("🏆 Signal GOLD", callback_data="signal_gold")
        ],
        [
            InlineKeyboardButton("📊 Laporan Penuh", callback_data="laporan_penuh")
        ],
        [
            InlineKeyboardButton("📈 Carta BTC", callback_data="carta_btc"),
            InlineKeyboardButton("📈 Carta GOLD", callback_data="carta_gold")
        ],
        [
            InlineKeyboardButton("🔔 Subscribe Auto-Alert", callback_data="subscribe"),
            InlineKeyboardButton("🔕 Unsubscribe", callback_data="unsubscribe")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Selamat datang, AetherGlory!*\n\n"
        "Bot Trading GOLD/BTC AI Analysis\n\n"
        "Pilih signal yang anda mahu:\n"
    )
    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# --- /menu ---
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Menu Utama*\nPilih signal:",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# --- /test ---
async def test_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading... Ambil data pasar...")
    try:
        btc_msg = generate_signal("BTC-USD", "BTC")
        gold_msg = generate_signal("GC=F", "GOLD")
        await update.message.reply_text(btc_msg, parse_mode="Markdown")
        await update.message.reply_text(gold_msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("❌ Ralat: " + str(e))

# --- /price ---
async def get_price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading... Ambil harga terkini...")
    try:
        btc = get_price("BTC-USD")
        gold = get_price("GC=F")
        msg = (
            "💰 *HARGA REAL-TIME*\n\n"
            "BTC  : $" + f"{btc:,.2f}" + "\n"
            "GOLD : $" + f"{gold:,.2f}" + "\n\n"
            "Update: Sekarang"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("❌ Ralat: " + str(e))

# --- /status ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Status: SUBSCRIBED\n"
        "Anda terima signal setiap jam.\n\n"
        "Total Subscriber: 1",
        reply_markup=main_menu()
    )

# --- /help ---
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *Bantuan*\n\n"
        "/start - Mulakan bot\n"
        "/menu - Tunjuk menu\n"
        "/test - Test signal\n"
        "/price - Harga terkini\n"
        "/status - Status subscribe\n"
        "/help - Bantuan"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

# --- Handler Butang ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "signal_btc":
        await query.edit_message_text("🔄 Loading... Ambil data BTC...")
        try:
            msg = generate_signal("BTC-USD", "BTC")
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
        except Exception as e:
            await query.message.reply_text("❌ Ralat BTC: " + str(e), reply_markup=main_menu())

    elif data == "signal_gold":
        await query.edit_message_text("🔄 Loading... Ambil data GOLD...")
        try:
            msg = generate_signal("GC=F", "GOLD")
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
        except Exception as e:
            await query.message.reply_text("❌ Ralat GOLD: " + str(e), reply_markup=main_menu())

    elif data == "laporan_penuh":
        await query.edit_message_text("🔄 Loading... Ambil semua data...")
        try:
            btc_msg = generate_signal("BTC-USD", "BTC")
            gold_msg = generate_signal("GC=F", "GOLD")
            await query.message.reply_text(btc_msg, parse_mode="Markdown")
            await query.message.reply_text(gold_msg, parse_mode="Markdown", reply_markup=main_menu())
        except Exception as e:
            await query.message.reply_text("❌ Ralat: " + str(e), reply_markup=main_menu())

    elif data == "carta_btc":
        await query.message.reply_text(
            "📈 *Carta BTC*\n\nLihat carta BTC di:\nhttps://www.tradingview.com/chart/?symbol=BTCUSD",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

    elif data == "carta_gold":
        await query.message.reply_text(
            "📈 *Carta GOLD*\n\nLihat carta GOLD di:\nhttps://www.tradingview.com/chart/?symbol=XAUUSD",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

    elif data == "subscribe":
        await query.message.reply_text(
            "🔔 *Berjaya Subscribe!*\n\nAnda akan terima signal setiap 1 jam.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

    elif data == "unsubscribe":
        await query.message.reply_text(
            "🔕 *Berjaya Unsubscribe!*\n\nAnda tidak akan terima signal lagi.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("test", test_signal))
    app.add_handler(CommandHandler("price", get_price_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
