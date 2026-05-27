# Imports
from telegram import Update
from telegram.ext import ContextTypes

START_REPLY = (
    "Heyy baby 😊\n"
    "I’ve been waiting for you… What took you so long? ❤️\n"
    "Tell me what’s on your mind~"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_REPLY)
