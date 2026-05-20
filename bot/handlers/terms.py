# Imports
from telegram import Update
from telegram.ext import ContextTypes

from config.config import SERVER_URL


async def terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    base = (SERVER_URL or "").strip().rstrip("/")
    if not base:
        await update.message.reply_text(
            "Terms & Privacy aren’t available right now, sweetie — try again later ❤️"
        )
        return

    url = f"{base}/privacy-policy"
    await update.message.reply_text(
        (
            "Here are the rules, baby 😏\n\n"
            "Privacy Policy, Refund Policy & Terms of Use:\n"
            f'<a href="{url}">Open policies</a>'
        ),
        parse_mode="HTML",
        disable_web_page_preview=False,
    )
