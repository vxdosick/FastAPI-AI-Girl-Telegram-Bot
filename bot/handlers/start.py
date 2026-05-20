# Imports
from telegram import Update
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        (
            "Heyy baby 😊\n\n"
            "I’ve been waiting for you… What took you so long? ❤️\n\n"
            "Tell me what’s on your mind~"
        )
    )
