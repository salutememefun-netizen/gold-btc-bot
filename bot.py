import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from analyzer import generate_signal, get_price, check_zone_alert
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUBSCRIBERS = set()

# --- Menu Butang Utama ---
def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🟢 Signal BTC", callback_data="signal_btc"),
            InlineKeyboardButton("🏆 Signal GOLD", callback_data="signal_gold")
        ],
        [InlineKeyboardButton("📊 Laporan Penuh", callback_data="laporan_penuh")],
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
    msg = "👋 *Selamat datang, AetherGlory!*\n\nBot Trading GOLD/BTC AI Analysis\n\nPilih signal yang anda mahu:\n"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

# --- /menu ---
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 *Menu Utama*\nPilih signal:", parse_mode="Markdown", reply_markup=main_menu())

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
        msg = f"💰 *HARGA REAL-TIME*\n\nBTC: ${btc:,.2f}\nGOLD: ${gold:,.2f}\n\nUpdate: Sekarang"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("❌ Ralat: " + str(e))

# --- /status ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_sub = "✅ SUBSCRIBED" if user_id in SUBSCRIBERS else "❌ NOT SUBSCRIBED"
    await update.message.reply_text(f"Status: {is_sub}\nAnda akan terima signal setiap jam jika subscribed.", reply_markup=main_menu())

# --- /help ---
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📖 *Bantuan*\n\n/start - Mulakan bot\n/menu - Tunjuk menu\n/test - Test signal\n/price - Harga terkini\n/status - Status subscribe\n/help - Bantuan"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

# --- Button Handler ---
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
        user_id = update.effective_user.id
        SUBSCRIBERS.add(user_id)
        await query.message.reply_text(
            "🔔 *Berjaya Subscribe!*\n\nAnda akan terima signal setiap 1 jam.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

    elif data == "unsubscribe":
        user_id = update.effective_user.id
        SUBSCRIBERS.discard(user_id)
        await query.message.reply_text(
            "🔕 *Berjaya Unsubscribe!*\n\nAnda tidak akan terima signal lagi.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

# --- Auto-Signal Function (dengan Logik Zon Alert) ---
async def send_auto_signal():
    print(f"[{datetime.now()}] Menghantar signal auto kepada subscriber...")
    if not SUBSCRIBERS:
        print("Tiada subscriber.")
        return

    try:
        # Semak status zon untuk BTC dan GOLD
        btc_active, btc_type, btc_entry, btc_tp, btc_sl = check_zone_alert("BTC-USD", "BTC")
        gold_active, gold_type, gold_entry, gold_tp, gold_sl = check_zone_alert("GC=F", "GOLD")

        for user_id in SUBSCRIBERS:
            try:
                # --- Hantar Alert BTC Jika Zon Aktif ---
                if btc_active:
                    alert_msg = (
                        f"🚨 *ALERT ZON ENTRY AKTIF: BTC*\n\n"
                        f"📊 *Zon:* {btc_type}\n"
                        f"💰 *Entry:* ${btc_entry:,.2f}\n"
                        f"🎯 *Take Profit:* ${btc_tp:,.2f}\n"
                        f"🛑 *Stop Loss:* ${btc_sl:,.2f}\n\n"
                        f"💡 *Harga semasa berada dalam zon!* Pertimbangkan entry.\n\n"
                        f"_(Dijana: {datetime.now().strftime('%H:%M')})_"
                    )
                    await context.bot.send_message(chat_id=user_id, text=alert_msg, parse_mode="Markdown")
                else:
                    # Jika zon tak aktif, hantar signal penuh
                    msg = generate_signal("BTC-USD", "BTC")
                    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")

                # --- Hantar Alert GOLD Jika Zon Aktif ---
                if gold_active:
                    alert_msg = (
                        f"🚨 *ALERT ZON ENTRY AKTIF: GOLD*\n\n"
                        f"📊 *Zon:* {gold_type}\n"
                        f"💰 *Entry
