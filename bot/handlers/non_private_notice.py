# Answer only in private chat — when explicitly mentioned (@nick or reply to bot's message).
from telegram import Message, Update
from telegram.constants import ChatType, MessageEntityType
from telegram.ext import ContextTypes

ONLY_PRIVATE_REPLY = "I only reply in private chat ❤️"


def _snippet(text: str, entity) -> str:
    return text[entity.offset : entity.offset + entity.length]


def _message_explicitly_addresses_bot(message: Message, bot_id: int, bot_username: str) -> bool:
    reply = message.reply_to_message
    if reply is not None and reply.from_user is not None and reply.from_user.id == bot_id:
        return True

    uname = (bot_username or "").strip().lstrip("@").lower()
    for text, entities in (
        (message.text, message.entities),
        (message.caption, message.caption_entities),
    ):
        if not text or not entities:
            continue
        for ent in entities:
            if ent.type == MessageEntityType.MENTION:
                if uname and _snippet(text, ent).strip().lstrip("@").lower() == uname:
                    return True
            elif ent.type == MessageEntityType.TEXT_MENTION:
                if ent.user and ent.user.id == bot_id:
                    return True
            elif ent.type == MessageEntityType.BOT_COMMAND:
                fragment = _snippet(text, ent).strip().lower()
                if uname and f"@{uname}" in fragment:
                    return True
    return False


async def only_private_notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat is None or chat.type == ChatType.PRIVATE:
        return

    msg = update.effective_message
    if msg is None:
        return

    bot_id = context.bot.id
    username = getattr(context.bot, "username", None) or ""

    if not _message_explicitly_addresses_bot(msg, bot_id, username):
        return

    await msg.reply_text(ONLY_PRIVATE_REPLY)
