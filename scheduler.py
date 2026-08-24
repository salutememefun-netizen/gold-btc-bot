from apscheduler.schedulers.asyncio import AsyncIOScheduler
from helpers import analyze_gold_btc
import logging

logger = logging.getLogger(__name__)

# Simpan chat_id user yang subscribe
subscribed_users = set()

def add_subscriber(chat_id):
    subscribed_users.add(chat_id)

def remove_subscriber(chat_id):
    subscribed_users.discard(chat_id)

async def auto_alert_job(application):
    """Hantar signal automatik setiap 1 jam"""
    logger.info("Menghantar auto-alert...")
    message = analyze_gold_btc()
    
    for chat_id in subscribed_users:
        try:
            await application.bot.send_message(
                chat_id=chat_id, 
                text=message, 
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Gagal hantar ke {chat_id}: {e}")

def setup_scheduler(application):
    """Mula scheduler"""
    scheduler = AsyncIOScheduler()
    # Jalankan setiap 1 jam (3600 saat)
    scheduler.add_job(
        auto_alert_job, 
        'interval', 
        hours=1, 
        args=[application],
        id='auto_alert',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler auto-alert bermula. Alert setiap 1 jam.")
