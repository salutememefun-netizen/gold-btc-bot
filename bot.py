#!/usr/bin/env python3
"""
Script alert untuk Railway Cron.
Jalankan setiap 1 jam.
"""

import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

# Import dari helpers
from helpers import (
    generate_ultimate_signal,
    get_binance_candles,
    get_all_subscribers,
    init_db
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def send_alerts():
    """Hantar alert Ultimate ke semua subscriber"""
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN tidak dijumpai!")
        return

    # Initialize DB
    init_db()
    
    # Dapatkan subscriber
    subscribers = get_all_subscribers()
    if not subscribers:
        print("Tiada subscriber.")
        return

    print(f"Mengirim alert ke {len(subscribers)} subscriber...")

    # Dapatkan signal BTC (sebagai contoh utama)
    candles = get_binance_candles("BTC", "1h", 50)
    message = "⚠️ Data tidak tersedia."
    
    if candles:
        price = candles[-1]["close"]
        message = generate_ultimate_signal("BTC", price)
    
    # Hantar ke semua subscriber
    bot = Bot(token=TOKEN)
    success = 0
    failed = 0
    
    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="⏰ *ALERT ULTIMATE (Setiap 1 Jam)*\n\n" + message,
                parse_mode='Markdown'
            )
            success += 1
            print(f"✅ Hantar ke {chat_id}")
        except Exception as e:
            print(f"❌ Gagal ke {chat_id}: {e}")
            failed += 1
    
    print(f"Siap! Success: {success}, Failed: {failed}")

if __name__ == '__main__':
    asyncio.run(send_alerts())
