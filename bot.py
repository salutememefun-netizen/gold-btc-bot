import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from analyzer import generate_signal, get_price, check_zone_alert
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUBSCRIBERS = {}
ALERT_CACHE = {}

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("Signal BTC", callback_data="signal_btc"),
            InlineKeyboardButton("Signal GOLD", callback_data="signal_gold")
        ],
        [InlineKeyboardButton("Laporan Penuh", callback_data="laporan_penuh")],
        [
            InlineKeyboardButton("Carta BTC", callback_data="carta_btc"),
            InlineKeyboardButton("Carta GOLD", callback_data="carta_gold")
        ],
        [
            InlineKeyboardButton("BTC Alert ON", callback_data="btc_alert_on"),
            InlineKeyboardButton("BTC Alert OFF", callback_data="btc_alert_off")
        ],
        [
            InlineKeyboardButton("GOLD Alert ON", callback_data="gold_alert_on"),
            InlineKeyboardButton("GOLD Alert OFF", callback_data="gold_alert_off")
        ],
        [
            InlineKeyboardButton("Subscribe", callback_data="subscribe"),
            InlineKeyboardButton("Unsubscribe", callback_data="unsubscribe")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "Selamat datang AetherGlory. Bot Trading GOLD/BTC AI Analysis. Pilih signal:"
    await update.message.reply_text(msg, reply_markup=main_menu())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menu Utama. Pilih signal:", reply_markup=main_menu())

async def test_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Loading signal...")
    try:
        btc_msg = generate_signal("BTC-USD", "BTC")
        gold_msg = generate_signal("GC=F", "GOLD")
        await update.message.reply_text(btc_msg, parse_mode="Markdown")
        await update.message.reply_text(gold_msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("Ralat: " + str(e))

async def get_price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Loading harga...")
    try:
        btc = get_price("BTC-USD")
        gold = get_price("GC=F")
        msg = "HARGA REAL-TIME\n\nBTC: $" + str(btc) + "\nGOLD: $" + str(gold)
        await update.message.reply_text(msg, reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("Ralat: " + str(e))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in SUBSCRIBERS:
        btc_status = "ON" if SUBSCRIBERS[user_id].get("btc_alert", False) else "OFF"
        gold_status = "ON" if SUBSCRIBERS[user_id].get("gold_alert", False) else "OFF"
        msg = "Status:\nBTC Alert: " + btc_status + "\nGOLD Alert: " + gold_status
    else:
        msg = "Status: NOT SUBSCRIBED"
    await update.message.reply_text(msg, reply_markup=main_menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "Bantuan\n/start - Mulakan\n/menu - Menu\n/test - Test\n/price - Harga\n/status - Status\n/help - Bantuan"
    await update.message.reply_text(msg, reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "signal_btc":
        await query.edit_message_text("Loading BTC...")
        try:
            msg = generate_signal("BTC-USD", "BTC")
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
        except Exception as e:
            await query.message.reply_text("Ralat: " + str(e), reply_markup=main_menu())

    elif data == "signal_gold":
        await query.edit_message_text("Loading GOLD...")
        try:
            msg = generate_signal("GC=F", "GOLD")
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
        except Exception as e:
            await query.message.reply_text("Ralat: " + str(e), reply_markup=main_menu())

    elif data == "laporan_penuh":
        await query.edit_message_text("Loading semua data...")
        try:
            btc_msg = generate_signal("BTC-USD", "BTC")
            gold_msg = generate_signal("GC=F", "GOLD")
            await query.message.reply_text(btc_msg, parse_mode="Markdown")
            await query.message.reply_text(gold_msg, parse_mode="Markdown", reply_markup=main_menu())
        except Exception as e:
            await query.message.reply_text("Ralat: " + str(e), reply_markup=main_menu())

    elif data == "carta_btc":
        await query.message.reply_text("Carta BTC: https://www.tradingview.com/chart/?symbol=BTCUSD", reply_markup=main_menu())

    elif data == "carta_gold":
        await query.message.reply_text("Carta GOLD: https://www.tradingview.com/chart/?symbol=XAUUSD", reply_markup=main_menu())

    elif data == "btc_alert_on":
        if user_id not in SUBSCRIBERS:
            SUBSCRIBERS[user_id] = {"btc_alert": False, "gold_alert": False}
        SUBSCRIBERS[user_id]["btc_alert"] = True
        await query.message.reply_text("BTC Alert ON. Anda akan dapat notifikasi BTC.", reply_markup=main_menu())

    elif data == "btc_alert_off":
        if user_id not in SUBSCRIBERS:
            SUBSCRIBERS[user_id] = {"btc_alert": False, "gold_alert": False}
        SUBSCRIBERS[user_id]["btc_alert"] = False
        await query.message.reply_text("BTC Alert OFF.", reply_markup=main_menu())

    elif data == "gold_alert_on":
        if user_id not in SUBSCRIBERS:
            SUBSCRIBERS[user_id] = {"btc_alert": False, "gold_alert": False}
        SUBSCRIBERS[user_id]["gold_alert"] = True
        await query.message.reply_text("GOLD Alert ON. Anda akan dapat notifikasi GOLD.", reply_markup=main_menu())

    elif data == "gold_alert_off":
        if user_id not in SUBSCRIBERS:
            SUBSCRIBERS[user_id] = {"btc_alert": False, "gold_alert": False}
        SUBSCRIBERS[user_id]["gold_alert"] = False
        await query.message.reply_text("GOLD Alert OFF.", reply_markup=main_menu())

    elif data == "subscribe":
        SUBSCRIBERS[user_id] = {"btc_alert": True, "gold_alert": True}
        await query.message.reply_text("Berjaya Subscribe. Alert BTC & GOLD ON.", reply_markup=main_menu())

    elif data == "unsubscribe":
        if user_id in SUBSCRIBERS:
            del SUBSCRIBERS[user_id]
        await query.message.reply_text("Berjaya Unsubscribe.", reply_markup=main_menu())

async def check_zone_and_alert(app):
    """Fungsi untuk check zon dan hantar alert"""
    print("Checking zone alert...")
    
    if not SUBSCRIBERS:
        return

    try:
        btc_active, btc_type, btc_entry, btc_tp, btc_sl = check_zone_alert("BTC-USD", "BTC")
        gold_active, gold_type, gold_entry, gold_tp, gold_sl = check_zone_alert("GC=F", "GOLD")

        for user_id, settings in SUBSCRIBERS.items():
            try:
                # Check BTC Zone
                if settings.get("btc_alert", False) and btc_active:
                    key = "btc_" + str(btc_type)
                    if key not in ALERT_CACHE or ALERT_CACHE[key] == False:
                        alert_msg = "🚨 ALERT ZON ENTRY AKTIF BTC\nZon: " + str(btc_type) + "\nEntry: $" + str(btc_entry) + "\nTP: $" + str(btc_tp) + "\nSL: $" + str(btc_sl) + "\n\nHarga semasa berada dalam zon!"
                        await app.bot.send_message(chat_id=user_id, text=alert_msg)
                        ALERT_CACHE[key] = True
                        print("Alert BTC sent to " + str(user_id))
                else:
                    ALERT_CACHE["btc_BUY"] = False
                    ALERT_CACHE["btc_SELL"] = False

                # Check GOLD Zone
                if settings.get("gold_alert", False) and gold_active:
                    key = "gold_" + str(gold_type)
                    if key not in ALERT_CACHE or ALERT_CACHE[key] == False:
                        alert_msg = "🚨 ALERT ZON ENTRY AKTIF GOLD\nZon: " + str(gold_type) + "\nEntry: $" + str(gold_entry) + "\nTP: $" + str(gold_tp) + "\nSL: $" + str(gold_sl) + "\n\nHarga semasa berada dalam zon!"
                        await app.bot.send_message(chat_id=user_id, text=alert_msg)
                        ALERT_CACHE[key] = True
                        print("Alert GOLD sent to " + str(user_id))
                else:
                    ALERT_CACHE["gold_BUY"] = False
                    ALERT_CACHE["gold_SELL"] = False

            except Exception as e:
                print("Gagal hantar alert ke " + str(user_id) + ": " + str(e))

    except Exception as e:
        print("Ralat check zone: " + str(e))

def setup_alert_scheduler(app):
    """Setup scheduler untuk check zone setiap 5 minit"""
    scheduler = BackgroundScheduler()
    
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(check_zone_and_alert(app))
        loop.close()
    
    scheduler.add_job(run_async, 'interval', minutes=5, id='zone_alert')
    scheduler.start()
    print("Alert scheduler started - checking every 5 minutes")
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

    setup_alert_scheduler(app)
    app.run_polling()

if __name__ == "__main__":
    main()
