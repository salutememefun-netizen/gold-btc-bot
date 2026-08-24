# ... import sedia ada ...
from scheduler import setup_scheduler, add_subscriber, remove_subscriber

# ... fungsi start dan button_handler sedia ada ...

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User subscribe untuk dapat auto-alert"""
    chat_id = update.effective_chat.id
    add_subscriber(chat_id)
    await update.message.reply_text("✅ Anda telah subscribe! Anda akan dapat signal automatik setiap 1 jam.")

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User unsubscribe"""
    chat_id = update.effective_chat.id
    remove_subscriber(chat_id)
    await update.message.reply_text("❌ Anda telah unsubscribe. Anda tidak akan terima alert lagi.")

def main():
    # ... kod sedia ada ...
    application = Application.builder().token(TOKEN).build()
    
    # Daftar handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command)) # BARU
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command)) # BARU
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Mula Scheduler
    setup_scheduler(application) # BARU
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
