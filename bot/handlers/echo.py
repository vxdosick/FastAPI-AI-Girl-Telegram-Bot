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
from services.image_gen import generate_image
from services.llm_utils import extract_assistant_text

from config.config import MESSAGES_AI_MODEL, OPENAI_API_KEY, OPENROUTER_BASE_URL

TG_TEXT_LIMIT = 4096
MAX_USER_MESSAGE_CHARS = 500
MAX_ASSISTANT_REPLY_CHARS = 650
RATE_LIMIT_COOLDOWN_SEC = 1.2
GENIMG_PREFIX = "genimg"
GENIMG_WARNING_MARKER = "warning: need genimg"

log = logging.getLogger(__name__)

TOO_LONG_USER_REPLY = (
    "Mmm, that was a bit too long, baby 😌\n"
    "Make it shorter for me? (max 500 characters)🍓"
)

GENIMG_HINT_REPLY = (
    "Mmm, got it, baby 🍓\n"
    "If I wanna send you a cute strawberry pic, I’ll just start the message with genimg "
    "and tell you exactly what kind of picture I want, my kitty 😌"
)

IMAGE_FAIL_REPLY = (
    "Mmm baby… I couldn’t draw that one 🥺 "
    "Try asking for something else, kitten — like a cozy anime selfie in a dress 💕"
)

NO_IMAGE_CREDITS_REPLY = (
    "I’d love to draw for you, baby… but you’re out of anime picture credits 🎨💔 "
    "Check /credits to grab more~"
)

GENIMG_EMPTY_REPLY = (
    "Tell me what to draw, baby~ Start your message with genimg and describe the scene, "
    "like: genimg cozy anime selfie in a red dress 💕"
)

LLM_ERROR_REPLY = (
    "My head got a little dizzy for a second… message me again? 🥺"
)

user_locks: dict[str, asyncio.Lock] = {}


def get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


def parse_genimg_prompt(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw.lower().startswith(GENIMG_PREFIX):
        return None
    prompt = raw[len(GENIMG_PREFIX) :].strip()
    if prompt.startswith(":"):
        prompt = prompt[1:].strip()
    return prompt


def is_genimg_warning(reply: str) -> bool:
    normalized = (reply or "").strip().lower()
    if not normalized:
        return False
    return normalized == GENIMG_WARNING_MARKER or normalized.startswith(f"{GENIMG_WARNING_MARKER}")


def _cap_assistant_reply(text: str, max_len: int = MAX_ASSISTANT_REPLY_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text

    cut = text[:max_len]
    for sep in ("\n\n", "\n", ". ", "! ", "? ", " "):
        idx = cut.rfind(sep)
        if idx > max_len // 2:
            return cut[:idx].rstrip()
    return cut.rstrip()


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


async def _send_generated_image(
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


async def _handle_genimg(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    chat_id: int,
    user_text: str,
) -> None:
    image_prompt = parse_genimg_prompt(user_text)
    if not image_prompt:
        await update.message.reply_text(GENIMG_EMPTY_REPLY)
        return

    image_sent = await _send_generated_image(
        update, context, chat_id, user_id, image_prompt
    )
    if image_sent:
        await append_turn_then_maybe_roll(user_id, user_text, "(sent a photo)")


async def _handle_text_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    chat_id: int,
    user_text: str,
) -> None:
    user = await fetch_or_create_user(user_id)
    if user.credits <= 0:
        await update.message.reply_text(
            "We’re out of messages, baby 💔 Go to /credits and I’ll show you how to stay with me longer."
        )
        return

    short_term = await window_list(user_id)
    messages = build_llm_messages(user.memory_summary, short_term, user_text)

    client = AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENAI_API_KEY,
    )

    typing_task = asyncio.create_task(
        _repeat_chat_action(context, chat_id, ChatAction.TYPING)
    )
    try:
        completion = await client.chat.completions.create(
            model=MESSAGES_AI_MODEL,
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

    reply = extract_assistant_text(completion)
    if reply is None:
        log.warning("Chat completion returned no choices (model=%s)", MESSAGES_AI_MODEL)
        await update.message.reply_text(LLM_ERROR_REPLY)
        return

    raw_reply = reply.strip()
    if not raw_reply:
        await update.message.reply_text(
            "Something went wrong… message me again, I’m here 💕"
        )
        return

    if is_genimg_warning(raw_reply):
        visible_reply = GENIMG_HINT_REPLY
    else:
        visible_reply = _cap_assistant_reply(raw_reply)
        if not visible_reply:
            await update.message.reply_text(
                "Something went wrong… message me again, I’m here 💕"
            )
            return

    if not await deduct_one_credit(user_id):
        await update.message.reply_text(
            "You ran out of credits at the worst moment 😢 Check /credits"
        )
        return

    await append_turn_then_maybe_roll(user_id, user_text, visible_reply)

    for chunk in _split_reply(visible_reply):
        await update.message.reply_text(chunk)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    user_text = update.message.text or ""
    is_genimg = user_text.strip().lower().startswith(GENIMG_PREFIX)

    if is_genimg:
        image_prompt = parse_genimg_prompt(user_text)
        if image_prompt and len(image_prompt) > MAX_USER_MESSAGE_CHARS:
            await update.message.reply_text(TOO_LONG_USER_REPLY)
            return
    elif len(user_text) > MAX_USER_MESSAGE_CHARS:
        await update.message.reply_text(TOO_LONG_USER_REPLY)
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
        if is_genimg:
            await _handle_genimg(update, context, user_id, chat_id, user_text)
        else:
            await _handle_text_chat(update, context, user_id, chat_id, user_text)
