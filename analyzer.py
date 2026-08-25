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
        msg = f"💰 *HARGA REAL-TIME*\n\nBTC: ${btc:,.2f}\nGOLD: ${gold:,.2f}\n\nUpdate: Sekarang"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text("❌ Ralat: " + str(e))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_sub = "✅ SUBSCRIBED" if user_id in SUBSCRIBERS else "❌ NOT SUBSCRIBED"
    await update.message.reply_text(f"Status: {is_sub}\nAnda akan terima signal setiap jam jika subscribed.", reply_markup=main_menu())

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
        await query.message.reply_text("📈 *Carta BTC*\n\nLihat carta BTC di:\nhttps://www.tradingview.com/chart/?symbol=BTCUSD", parse_mode="Markdown", reply_markup=main_menu())

    elif data == "carta_gold":
        await query.message.reply_text
