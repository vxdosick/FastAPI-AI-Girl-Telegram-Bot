# Bot subclass that records outbound message IDs for chat purge on /delete_info.
from telegram import Bot, Message

from services.chat_messages import track_chat_message


class TrackedBot(Bot):
    async def _track_outgoing(self, message: Message | None) -> None:
        if message is None or message.chat is None:
            return
        chat = message.chat
        if chat.type != "private":
            return
        await track_chat_message(str(chat.id), chat.id, message.message_id)

    async def send_message(self, *args, **kwargs):
        message = await super().send_message(*args, **kwargs)
        await self._track_outgoing(message)
        return message

    async def send_photo(self, *args, **kwargs):
        message = await super().send_photo(*args, **kwargs)
        await self._track_outgoing(message)
        return message

    async def send_invoice(self, *args, **kwargs):
        message = await super().send_invoice(*args, **kwargs)
        await self._track_outgoing(message)
        return message
