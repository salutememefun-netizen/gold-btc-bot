#!/usr/bin/env python3
import os, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from helpers import init_db, add_subscriber_db, remove_subscriber_db, get_all_subscribers, generate_ultimate_signal, get_btc_price, get_gold_price

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# AUTO DETECT TOKEN (Cuba semua nama yang mungkin)
BOT_TOKEN = (
    os.getenv("BOT_TOKEN") or
    os.getenv("TELEGRAM_BOT_TOKEN") or
    os.getenv("TELEGRAM_BOT_API") or
    os.getenv("TG_BOT_TOKEN") or
    os.getenv("TELEGRAM_TOKEN")
)

if not BOT_TOKEN:
    logger.error("❌ TIDAK ADA BOT_TOKEN! Senarai variable yang ada:")
    for k in os.environ:
        if 'TOKEN' in k.upper() or 'BOT' in k.upper():
            logger.error(f"   - {k}")
    exit(1)

logger.info(f"✅ Guna token: {BOT_TOKEN[:5]}...")

async def start(u, c):
    await u.message.reply_text(f"🤖 Hai {u.effective_user.first_name}! Bot jalan. Guna /help untuk senarai command.")

async def subscribe(u, c):
    if add_subscriber_db(u.effective_chat.id):
        await u.message.reply_text("✅ Berhasil Subscribe!")
    else:
        await u.message.reply_text("❌ Gagal.")

async def unsubscribe(u, c):
    if remove_subscriber_db(u.effective_chat.id):
        await u.message.reply_text("✅ Unsubscribe!")
    else:
        await u.message.reply_text("❌ Belum subscribe.")

async def test(u, c):
    await u.message.reply_text("🔄 Loading...")
    btc, gold = get_btc_price(), get_gold_price()
    if btc and gold:
        msg = f"💰 BTC: ${btc:,.2f}\n🟡 GOLD: ${gold:,.2f}\n\n{generate_ultimate_signal('BTC', btc)}"
        await u.message.reply_text(msg)
    else:
        await u.message.reply_text("❌ Gagal ambil data.")

async def status(u, c):
    subs = get_all_subscribers()
    st = "✅ SUBSCRIBED" if u.effective_chat.id in subs else "❌ NOT SUBSCRIBED"
    await u.message.reply_text(f"{st}\nTotal: {len(subs)}")

async def price(u, c):
    btc, gold = get_btc_price(), get_gold_price()
    if btc and gold:
        await u.message.reply_text(f"💰 BTC: ${btc:,.2f}\n🟡 GOLD: ${gold:,.2f}")
    else:
        await u.message.reply_text("❌ Gagal.")

async def err(u, c):
    logger.error(f"Error: {c.error}")

def main():
    logger.info("🚀 Start...")
    if not init_db():
        logger.error("❌ Gagal DB")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("price", price))
    app.add_error_handler(err)
    logger.info("✅ Bot ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
