# Imports
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from repositories.repositories import clear_user_stored_memory
from services.services import clear_chat_window

CALLBACK_DELETE_YES = "del_info_yes"
CALLBACK_DELETE_NO = "del_info_no"

CONFIRM_TEXT = (
    "Are you sure you want to delete all data about you stored in this bot?\n\n"
    "This will erase your chat memory and conversation summary. "
    "Your message credits and your anime picture generation credits will stay the same."
)


async def delete_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes, delete my data", callback_data=CALLBACK_DELETE_YES),
                InlineKeyboardButton("Cancel", callback_data=CALLBACK_DELETE_NO),
            ]
        ]
    )
    await update.message.reply_text(CONFIRM_TEXT, reply_markup=keyboard)


async def delete_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == CALLBACK_DELETE_NO:
        await query.edit_message_text("Cancelled. Nothing was deleted.")
        return

    if query.data != CALLBACK_DELETE_YES:
        return

    user_id = str(query.from_user.id)
    await clear_chat_window(user_id)
    await clear_user_stored_memory(user_id)

    await query.edit_message_text(
        "Done. All your saved memory in this bot has been cleared — "
        "your message credits and picture credits are unchanged. We can start fresh anytime 💕"
    )
