
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from helpers import analyze_gold_btc
import logging

logger = logging.getLogger(__name__)

# Simpan senarai chat_id yang subscribe
subscribed_users = set()

def add_subscriber(chat
