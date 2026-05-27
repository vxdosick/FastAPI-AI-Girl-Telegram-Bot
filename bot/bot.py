# Imports
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters
from telegram.constants import ChatType

from bot.tracked_bot import TrackedBot
from services.chat_messages import track_chat_message

# Handlers
from bot.handlers.start import start
from bot.handlers.help import help
from bot.handlers.credits import (
    credits,
    credits_pay_callback,
    credits_precheckout,
    credits_successful_payment,
)
from bot.handlers.terms import terms
from bot.handlers.echo import echo
from bot.handlers.unknown import unknown
from bot.handlers.contacts import contacts
from bot.handlers.delete_info import delete_info, delete_info_callback
from bot.handlers.non_private_notice import only_private_notice
from bot.handlers.errors import on_error

# Define tokens
from config.config import BOT_TOKEN

PRIVATE = filters.ChatType.PRIVATE

bot = TrackedBot(BOT_TOKEN)
app = Application.builder().bot(bot).concurrent_updates(True).build()


async def track_incoming_private_message(update, context):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user or chat.type != ChatType.PRIVATE:
        return
    await track_chat_message(str(user.id), chat.id, msg.message_id)


# Private chat: commands and conversation
app.add_handler(CommandHandler("start", start, filters=PRIVATE))
app.add_handler(CommandHandler("help", help, filters=PRIVATE))
app.add_handler(CommandHandler("credits", credits, filters=PRIVATE))
app.add_handler(CallbackQueryHandler(credits_pay_callback, pattern="^pay:"))
app.add_handler(PreCheckoutQueryHandler(credits_precheckout))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT & PRIVATE, credits_successful_payment))
app.add_handler(CommandHandler("terms", terms, filters=PRIVATE))
app.add_handler(CommandHandler("contacts", contacts, filters=PRIVATE))
app.add_handler(CommandHandler("delete_info", delete_info, filters=PRIVATE))
app.add_handler(
    CallbackQueryHandler(delete_info_callback, pattern="^del_info"),
)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & PRIVATE, echo))
app.add_handler(MessageHandler(filters.COMMAND & PRIVATE, unknown))
app.add_handler(
    MessageHandler(
        (~PRIVATE) & (filters.TEXT | filters.COMMAND | filters.Caption),
        only_private_notice,
    )
)
app.add_handler(MessageHandler(PRIVATE, track_incoming_private_message), group=1)
app.add_error_handler(on_error)
