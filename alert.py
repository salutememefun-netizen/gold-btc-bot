#!/usr/bin/env python3
"""
Script ini dijalankan oleh Railway Cron setiap 1 jam.
Ia akan hantar signal ke semua subscriber.
"""

import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv
from helpers import analyze_gold_btc, get_all_subscribers, init_db

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def send_alerts():
    """Hantar alert ke semua subscriber"""
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN tidak dijumpai!")
        return

    # Initialize DB
    init_db()
    
    # Dapatkan senarai subscriber
    subscribers = get_all_subscribers()
    if not subscribers:
        print("Tiada subscriber. Tiada alert dihantar.")
        return

    print(f"Mengirim alert ke {len(subscribers)} subscriber...")
    
    # Dapatkan laporan
    message = analyze_gold_btc()
    
    # Hantar ke setiap subscriber
    bot = Bot(token=TOKEN)
    success = 0
    failed = 0
    
    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="⏰ *Alert Automatik (Setiap 1 Jam)*\n\n" + message,
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
