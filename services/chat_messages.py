# Track private-chat message IDs in Redis so /delete_info can purge visible history.
from __future__ import annotations

import json

from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config.config import REDIS_KEY_PREFIX

from services import services as _svc


def _track_key(telegram_id: str) -> str:
    return f"{REDIS_KEY_PREFIX}:chat:{telegram_id}:message_ids"


async def track_chat_message(telegram_id: str, chat_id: int, message_id: int) -> None:
    if not _svc._redis or not message_id:
        return
    payload = json.dumps({"chat_id": chat_id, "message_id": message_id})
    key = _track_key(telegram_id)
    pipe = _svc._redis.pipeline(transaction=True)
    pipe.rpush(key, payload)
    pipe.ltrim(key, -500, -1)
    await pipe.execute()


async def clear_message_tracking(telegram_id: str) -> None:
    if not _svc._redis:
        return
    await _svc._redis.delete(_track_key(telegram_id))


async def purge_tracked_chat_messages(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: str,
    chat_id: int,
) -> int:
    """Delete tracked messages in Telegram; returns count of successful deletes."""
    if not _svc._redis:
        return 0

    key = _track_key(telegram_id)
    raw_items = await _svc._redis.lrange(key, 0, -1)
    deleted = 0

    for item in raw_items:
        try:
            obj = json.loads(item)
            mid = int(obj["message_id"])
            cid = int(obj.get("chat_id", chat_id))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        try:
            await context.bot.delete_message(chat_id=cid, message_id=mid)
            deleted += 1
        except TelegramError:
            continue

    await _svc._redis.delete(key)
    return deleted
