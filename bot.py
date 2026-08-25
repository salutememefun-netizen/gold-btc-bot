import os
import asyncio
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
            InlineKeyboardButton("Signal BTC", callback_data="signal_btc"),
            InlineKeyboardButton("Signal GOLD", callback_data="signal_gold")
        ],
        [InlineKeyboardButton("Laporan Penuh", callback_data="laporan_penuh")],
        [
            InlineKeyboardButton("Carta BTC", callback_data="carta_btc"),
            InlineKeyboardButton("Carta GOLD", callback_data="carta_gold")
        ],
        [
            InlineKeyboardButton("Subscribe", callback_data="subscribe"),
            InlineKeyboardButton("Unsubscribe", callback_data="unsubscribe")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start
