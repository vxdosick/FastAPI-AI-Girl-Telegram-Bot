# Global Telegram error handler — friendly replies instead of silent failures
import logging

from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

GENERIC_ERROR_REPLY = (
    "Something went wrong on my side, baby 🥺 "
    "Please try again in a moment — I’m still here for you 💕"
)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled bot error", exc_info=context.error)

    if not isinstance(update, Update):
        return

    message = update.effective_message
    if message is None:
        return

    try:
        await message.reply_text(GENERIC_ERROR_REPLY)
    except Exception:
        log.exception("Failed to send error reply to user")
