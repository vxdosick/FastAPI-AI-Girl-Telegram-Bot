# Imports
from telegram import Update
from telegram.ext import ContextTypes

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        (
            "Need a hand, sweetie? 😏\n\n"
            "/start — start chatting with me 🍓\n"
            "/help — show available commands 🤔\n"
            "/credits — check your messages/images generation credits and buy more ❤️‍🔥\n"
            "/terms — privacy, terms and refund policy 📜\n"
            "/contacts — contact support\n"
            "/delete_info — delete all saved chat memory (messages/images generation credits stay)"
        )
    )