import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from analyzer import generate_signal, get_price  # ✅ Tukar kepada analyzer

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Selamat datang, AetherGlory!\n\n"
        "Bot Trading GOLD/BTC AI Analysis\n\n"
        "📋 Perintah:\n"
        "/subscribe - Sinyal setiap 1 jam\n"
        "/unsubscribe - Berhenti\n"
        "/test - Test alert\n"
        "/status - Status\n"
        "/price - Harga real-time\n"
        "/help - Bantuan"
    )

async def test_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading... Ambil data pasar...")
    try:
        btc_msg = generate_signal("BTC-USD", "BTC")
        gold_msg = generate_signal("GC=F", "GOLD")
        await update.message.reply_text(btc_msg)
        await update.message.reply_text(gold_msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Ralat: {e}")

async def get_price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Loading... Ambil harga terkini...")
    try:
        btc = get_price("BTC-USD")
        gold = get_price("GC=F")
        msg = f"💰 *HARGA REAL-TIME*\n\nBTC: ${btc:,.2f}\nGOLD: ${gold:,.2f}\n\nUpdate: Sekarang"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Ralat: {e}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Status: SUBSCRIBED\nAnda terima signal setiap jam.\n\nTotal Subscriber: 1")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Berjaya subscribe!")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Berjaya unsubscribe!")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 Gunakan perintah /start untuk melihat senarai perintah.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_signal))
    app.add_handler(CommandHandler("price", get_price_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("help", help_cmd))
    app.run_polling()

if __name__ == "__main__":
    main()
