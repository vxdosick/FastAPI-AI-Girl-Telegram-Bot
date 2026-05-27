# Imports
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from repositories.repositories import clear_user_stored_memory
from services.chat_messages import purge_tracked_chat_messages, track_chat_message
from services.services import clear_chat_window

CALLBACK_DELETE_YES = "del_info_yes"
CALLBACK_DELETE_NO = "del_info_no"

CONFIRM_TEXT = (
    "Baby... you wanna wipe our whole chat and erase all your history with me? 😔\n\n"
    "Everything’s gonna disappear — every little thing I’ve told you about myself and all our messages.\n"
    "But don’t worry, your credits for messages and pictures will stay safe on your balance."
)


async def delete_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes, delete 💔", callback_data=CALLBACK_DELETE_YES),
                InlineKeyboardButton("Cancel 🚫", callback_data=CALLBACK_DELETE_NO),
            ]
        ]
    )
    await update.message.reply_text(CONFIRM_TEXT, reply_markup=keyboard)


async def delete_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == CALLBACK_DELETE_NO:
        await query.edit_message_text(
            "Deletion cancelled, baby 😌\n"
            "Ready to keep going, pupsy? 🫦"
            )
        return

    if query.data != CALLBACK_DELETE_YES:
        return

    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id

    await clear_chat_window(user_id)
    await clear_user_stored_memory(user_id)

    if query.message:
        await track_chat_message(user_id, chat_id, query.message.message_id)

    await purge_tracked_chat_messages(context, user_id, chat_id)
