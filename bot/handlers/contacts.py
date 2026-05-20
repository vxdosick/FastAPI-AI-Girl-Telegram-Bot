# Imports
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatType

from config.config import SUPPORT_TELEGRAM


def _support_handle_and_url():
    raw = (SUPPORT_TELEGRAM or "").strip()
    if not raw:
        return None, None
    display = raw if raw.startswith("@") else f"@{raw}"
    username = display.lstrip("@")
    if not username:
        return None, None
    return display, f"https://t.me/{username}"


async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    display, url = _support_handle_and_url()
    if url and display:
        await update.message.reply_text(
            f"Need help? 🙂\n\n"
            f"If something breaks, looks wrong, or you just want to reach the developer — "
            f"message me on Telegram:\n\n"
            f'<a href="{url}">{display}</a>',
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    else:
        await update.message.reply_text(
            f"Need help? 🙂\n\n"
            f"Support contact isn’t configured right now — please try again later."
        )