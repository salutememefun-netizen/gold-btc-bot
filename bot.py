import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from analyzer import generate_signal, get_price, check_zone_alert
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUBSCRIBERS = set()

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "👋 *Selamat datang, AetherGlory!*\n\nBot Trading GOLD/BTC AI Analysis\n\nPilih signal yang anda mahu:\n"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 *Menu Utama*\nPilih signal:", parse_mode="Markdown", reply_markup=main_menu())

async def test_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading... Ambil data pasar...")
    try:
        btc_msg = generate_signal("BTC-USD", "BTC")
        gold_msg = generate_signal("GC=F", "GOLD")
        await update.message.reply_text(btc_msg, parse_mode="Markdown")
        await update.message.reply_text(gold_msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("❌ Ralat: " + str(e))

async def get_price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading... Ambil harga terkini...")
    try:
        btc = get_price("BTC-USD")
        gold = get_price("GC=F")
        msg = "💰 *HARGA REAL-TIME*\n\nBTC: $" + f"{btc:,.2f}" + "\nGOLD: $" + f"{gold:,.2f}" + "\n\nUpdate: Sekarang"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("❌ Ralat: " + str(e))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_sub = "✅ SUBSCRIBED" if user_id in SUBSCRIBERS else "❌ NOT SUBSCRIBED"
    await update.message.reply_text("Status: " + is_sub + "\nAnda akan terima signal setiap jam jika subscribed.", reply_markup=main_menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📖 *Bantuan*\n\n/start - Mulakan bot\n/menu - Tunjuk menu\n/test - Test signal\n/price - Harga terkini\n/status - Status subscribe\n/help - Bantuan"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

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

async def send_auto_signal():
    print("[" + str(datetime.now()) + "] Menghantar signal auto kepada subscriber...")
    if not SUBSCRIBERS:
        print("Tiada subscriber.")
        return

    try:
        btc_active, btc_type, btc_entry, btc_tp, btc_sl = check_zone_alert("BTC-USD", "BTC")
        gold_active, gold_type, gold_entry, gold_tp, gold_sl = check_zone_alert("GC=F", "GOLD")

        for user_id in SUBSCRIBERS:
            try:
                # BTC Alert
                if btc_active:
                    alert_msg = (
                        "🚨 *ALERT ZON ENTRY AKTIF: BTC*\n\n"
                        "📊 *Zon:* " + str(btc_type) + "\n"
                        "💰 *Entry:* $" + f"{btc_entry:,.2f}" + "\n"
                        "🎯 *Take Profit:* $" + f"{btc_tp:,.2f}" + "\n"
                        "🛑 *Stop Loss:* $" + f"{btc_sl:,.2f}" + "\n\n"
                        "💡 *Harga semasa berada dalam zon!* Pertimbangkan entry.\n\n"
                        "_(Dijana: " + datetime.now().strftime("%H:%M") + ")_"
                    )
                    await context.bot.send_message(chat_id=user_id, text=alert_msg, parse_mode="Markdown")
                else:
                    msg = generate_signal("BTC-USD", "BTC")
                    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")

                # GOLD Alert
                if gold_active:
                    alert_msg = (
                        "🚨 *ALERT ZON ENTRY AKTIF: GOLD*\n\n"
                        "📊 *Zon:* " + str(gold_type) + "\n"
                        "💰 *Entry:* $" + f"{gold_entry:,.2f}" + "\n"
                        "🎯 *Take Profit:* $" + f"{gold_tp:,.2f}" + "\n"
                        "🛑 *Stop Loss:* $" + f"{gold_sl:,.2f}" + "\n\n"
                        "💡 *Harga semasa berada dalam zon!* Pertimbangkan entry.\n\n"
                        "_(Dijana: " + datetime.now().strftime("%H:%M") + ")_"
                    )
                    await context.bot.send_message(chat_id=user_id, text=alert_msg, parse_mode="Markdown")
                else:
                    msg = generate_signal("GC=F", "GOLD")
                    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")

                print("Signal/Alert dihantar kepada " + str(user_id))

            except Exception as e:
                print("Gagal hantar ke " + str(user_id) + ": " + str(e))

    except Exception as e:
        print("Ralat menjana signal auto: " + str(e))

def setup_scheduler(application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_auto_signal, 'cron', hour='*', minute=0)
    scheduler.start()
    return scheduler

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("test", test_signal))
    app.add_handler(CommandHandler("price", get_price_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    setup_scheduler(app)
    app.run_polling()

if __name__ == "__main__":
    main()
