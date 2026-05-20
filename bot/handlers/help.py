# Imports
from telegram import Update
from telegram.ext import ContextTypes

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        (
            "Need a hand, sweetie? 😏\n\n"
            "/start — start chatting with me\n"
            "/help — show available commands\n"
            "/credits — check your messages and buy more\n"
            "/terms — privacy, terms and refund policy\n"
            "/contacts — contact support or the developer\n"
            "/delete_info — delete all saved chat memory (credits stay)"
        )
    )