# Imports
from telegram import Update
from telegram.ext import ContextTypes

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Mmm, I don’t know that command, baby 😌\n"
        "Try /help sweetie~"
    )