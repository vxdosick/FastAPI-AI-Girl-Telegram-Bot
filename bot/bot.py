# Imports
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters
from telegram import Bot

# Handlers
from bot.handlers.start import start
from bot.handlers.help import help
from bot.handlers.credits import credits
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

# TB App creating
bot = Bot(BOT_TOKEN)
app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

# Private chat: commands and conversation
app.add_handler(CommandHandler("start", start, filters=PRIVATE))
app.add_handler(CommandHandler("help", help, filters=PRIVATE))
app.add_handler(CommandHandler("credits", credits, filters=PRIVATE))
app.add_handler(CommandHandler("terms", terms, filters=PRIVATE))
app.add_handler(CommandHandler("contacts", contacts, filters=PRIVATE))
app.add_handler(CommandHandler("delete_info", delete_info, filters=PRIVATE))
app.add_handler(
    CallbackQueryHandler(delete_info_callback, pattern="^del_info"),
)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & PRIVATE, echo))
app.add_handler(MessageHandler(filters.COMMAND & PRIVATE, unknown))
# Groups / channels: answer only when @nick or reply to bot's message
app.add_handler(
    MessageHandler(
        (~PRIVATE) & (filters.TEXT | filters.COMMAND | filters.Caption),
        only_private_notice,
    )
)
app.add_error_handler(on_error)
