# Imports
import asyncio
import logging
from io import BytesIO

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from openai import AsyncOpenAI

from bot.utils.is_rate_limited import is_rate_limited
from repositories.repositories import (
    deduct_one_credit,
    deduct_one_image_credit,
    fetch_or_create_user,
)
from services.services import append_turn_then_maybe_roll, build_llm_messages, window_list
from services.image_gen import (
    fallback_image_prompt_from_user,
    generate_image,
    split_reply_and_image_prompt,
    user_likely_wants_image,
)
from services.llm_utils import extract_assistant_text

from config.config import AI_MODEL, OPENAI_API_KEY, OPENROUTER_BASE_URL

TG_TEXT_LIMIT = 4096
RATE_LIMIT_COOLDOWN_SEC = 1.2

log = logging.getLogger(__name__)

IMAGE_FAIL_REPLY = (
    "Mmm baby… I couldn’t draw that one 🥺 "
    "Try asking for something else, kitten — like a cozy anime selfie in a dress 💕"
)

NO_IMAGE_CREDITS_REPLY = (
    "I’d love to draw for you, baby… but you’re out of anime picture credits 🎨💔 "
    "Check /credits — for now you can still chat with me in text~"
)

LLM_ERROR_REPLY = (
    "My head got a little dizzy for a second… message me again? 🥺"
)

user_locks: dict[str, asyncio.Lock] = {}


def get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


def _split_reply(text: str, max_len: int = TG_TEXT_LIMIT) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts: list[str] = []
    while text:
        parts.append(text[:max_len])
        text = text[max_len:]
    return parts


async def _repeat_chat_action(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    action: ChatAction,
) -> None:
    try:
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action=action)
            await asyncio.sleep(4.5)
    except asyncio.CancelledError:
        return


async def _try_send_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: str,
    image_prompt: str,
) -> bool:
    """Generate and send photo. Deducts one image credit only after a successful send."""
    user = await fetch_or_create_user(user_id)
    if user.image_generating <= 0:
        await update.message.reply_text(NO_IMAGE_CREDITS_REPLY)
        return False

    upload_task = asyncio.create_task(
        _repeat_chat_action(context, chat_id, ChatAction.UPLOAD_PHOTO)
    )
    try:
        image_bytes = await generate_image(image_prompt)
    finally:
        upload_task.cancel()
        try:
            await upload_task
        except asyncio.CancelledError:
            pass

    if not image_bytes:
        await update.message.reply_text(IMAGE_FAIL_REPLY)
        return False

    if not await deduct_one_image_credit(user_id):
        await update.message.reply_text(NO_IMAGE_CREDITS_REPLY)
        return False

    await update.message.reply_photo(photo=BytesIO(image_bytes))
    return True


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id

    if len(update.message.text) > 800:
        await update.message.reply_text(
            "That message is a little too long, baby 😅 Keep it under 800 characters so I can answer you properly."
        )
        return

    if is_rate_limited(user_id, cooldown=RATE_LIMIT_COOLDOWN_SEC):
        await update.message.reply_text(
            "Slow down a little, baby… 💖 I’m right here — give me a second between messages."
        )
        return

    lock = get_user_lock(user_id)
    if lock.locked():
        await update.message.reply_text(
            "Wait a second, baby… I’m still answering your last message 💖"
        )
        return

    async with lock:
        user = await fetch_or_create_user(user_id)

        if user.credits <= 0:
            await update.message.reply_text(
                "We’re out of messages, baby 💔 Go to /credits and I’ll show you how to stay with me longer."
            )
            return

        short_term = await window_list(user_id)
        messages = build_llm_messages(user.memory_summary, short_term, update.message.text)

        client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENAI_API_KEY,
        )

        typing_task = asyncio.create_task(
            _repeat_chat_action(context, chat_id, ChatAction.TYPING)
        )
        try:
            completion = await client.chat.completions.create(
                model=AI_MODEL,
                messages=messages,
                extra_body={},
            )
        except Exception:
            log.exception("Chat completion failed for user_id=%s", user_id)
            await update.message.reply_text(LLM_ERROR_REPLY)
            return
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

        user_text = update.message.text
        wants_image = user_likely_wants_image(user_text)
        reply = extract_assistant_text(completion)

        if reply is None:
            log.warning("Chat completion returned no choices (model=%s)", AI_MODEL)
            if not wants_image:
                await update.message.reply_text(LLM_ERROR_REPLY)
                return
            visible_reply = "One sec, kitten… let me try to show you 💕"
            image_prompt = fallback_image_prompt_from_user(user_text)
        else:
            reply = reply.strip()
            visible_reply, image_prompt = split_reply_and_image_prompt(reply)
            if not visible_reply and not image_prompt and wants_image:
                visible_reply = "Here you go, baby… 📸"
                image_prompt = fallback_image_prompt_from_user(user_text)
            elif not image_prompt and wants_image:
                image_prompt = fallback_image_prompt_from_user(user_text)
            elif not reply and not wants_image:
                await update.message.reply_text(
                    "Something went wrong… message me again, I’m here 💕"
                )
                return

        # Picture path: generate and show first; image credit only after successful photo.
        image_sent = False
        if image_prompt:
            image_sent = await _try_send_image(
                update, context, chat_id, user_id, image_prompt
            )

        if not await deduct_one_credit(user_id):
            await update.message.reply_text(
                "You ran out of credits at the worst moment 😢 Check /credits"
            )
            return

        memory_reply = visible_reply or ("(sent a photo)" if image_sent else "")
        if image_prompt and not visible_reply and image_sent:
            memory_reply = "(sent a photo)"
        await append_turn_then_maybe_roll(user_id, user_text, memory_reply or "(reply)")

        for chunk in _split_reply(visible_reply):
            await update.message.reply_text(chunk)
