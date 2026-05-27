# Sliding-window chat memory (Redis), long-term summary roll-ups, and LLM message assembly
from __future__ import annotations
import json
import logging
import redis.asyncio as redis
from openai import AsyncOpenAI

from repositories.repositories import fetch_memory_summary, save_memory_summary

from config.config import (
    MEMORY_WINDOW_SIZE,
    MESSAGES_AI_MODEL,
    OPENAI_API_KEY,
    OPENROUTER_BASE_URL,
    REDIS_KEY_PREFIX,
    SHE_WANTS_YOU_PROMPT,
    SUMMARY_MODEL,
    SYSTEM_PROMPT,
)
from services.llm_utils import extract_assistant_text

log = logging.getLogger(__name__)

_redis: redis.Redis | None = None

GENIMG_INSTRUCTION = (
    "\n\n---\nPictures and anime art:\n"
    "- You cannot send images from normal chat.\n"
    "- If he asks for a photo, picture, drawing, selfie, or image generation WITHOUT starting "
    "his message with genimg, reply with exactly this line and nothing else: warning: need genimg\n"
    "- Do not explain genimg in your own words when he asks for a picture — use that exact line only.\n"
    "- Do not pretend you attached an image in text-only replies.\n"
)

SUMMARY_SYSTEM = (
    "You maintain one evolving summary of a user's romantic chat with a virtual girlfriend (18+).\n"
    "Merge the previous summary (if any) with the NEW message window below.\n"
    "Output exactly ONE updated summary in English with these headers:\n"
    "Facts about him:\n"
    "Key topics and events:\n"
    "Current relationship tone and emotions:\n"
    "Rules: adults 18+ only; omit illegal how-tos, minors, or graphic violent crime; keep it safe. Max ~600 words."
)


def redis_enabled() -> bool:
    return _redis is not None


async def init_redis(url: str | None) -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    if not (url and url.strip()):
        log.warning("REDIS_URL unset — sliding memory and rollups disabled")
        return
    _redis = redis.from_url(url.strip(), decode_responses=True)
    await _redis.ping()


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def _window_key(telegram_id: str) -> str:
    return f"{REDIS_KEY_PREFIX}:chat:{telegram_id}:window"


async def clear_chat_window(telegram_id: str) -> None:
    if not _redis:
        return
    await _redis.delete(_window_key(telegram_id))


def _parse_turns(raw_items: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw_items:
        try:
            obj = json.loads(item)
            if isinstance(obj, dict) and "role" in obj and "content" in obj:
                out.append({"role": str(obj["role"]), "content": str(obj["content"])})
        except json.JSONDecodeError:
            continue
    return out


async def window_list(telegram_id: str) -> list[dict[str, str]]:
    if not _redis:
        return []
    raw = await _redis.lrange(_window_key(telegram_id), 0, -1)
    return _parse_turns(raw)


async def append_turn_then_maybe_roll(
    telegram_id: str,
    user_text: str,
    assistant_text: str,
) -> None:
    if not _redis:
        return
    key = _window_key(telegram_id)
    pipe = _redis.pipeline(transaction=True)
    pipe.rpush(key, json.dumps({"role": "user", "content": user_text}, ensure_ascii=False))
    pipe.rpush(key, json.dumps({"role": "assistant", "content": assistant_text}, ensure_ascii=False))
    pipe.ltrim(key, -MEMORY_WINDOW_SIZE, -1)
    await pipe.execute()
    n = await _redis.llen(key)
    if n >= MEMORY_WINDOW_SIZE:
        await roll_long_term_memory(telegram_id)


async def roll_long_term_memory(telegram_id: str) -> None:
    if not _redis:
        return
    key = _window_key(telegram_id)
    raw = await _redis.lrange(key, 0, -1)
    if len(raw) < MEMORY_WINDOW_SIZE:
        return
    turns = _parse_turns(raw)
    old = await fetch_memory_summary(telegram_id)
    transcript = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
    client = AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENAI_API_KEY)
    model = SUMMARY_MODEL or MESSAGES_AI_MODEL
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM},
                {
                    "role": "user",
                    "content": f"Previous summary:\n{old or '(No information available yet)'}\n\nChat window:\n{transcript}",
                },
            ],
        )
        text = (extract_assistant_text(resp) or "").strip()
        if text:
            await save_memory_summary(telegram_id, text)
    except Exception:
        log.exception("Long-term memory rollup failed for user_id=%s", telegram_id)
    finally:
        await _redis.delete(key)


def build_llm_messages(
    long_summary: str,
    short_term: list[dict[str, str]],
    user_input: str,
) -> list[dict[str, str]]:
    # Build the system prompt
    blocks: list[str] = [
        SHE_WANTS_YOU_PROMPT,
        "\n\n---\nRules and boundaries:\n",
        SYSTEM_PROMPT,
    ]
    summary = (long_summary or "").strip()
    if summary:
        blocks.append(f"\n\n### Long-term memory (summary)\n{summary}")
    if short_term:
        lines = [f"{m['role']}: {m['content']}" for m in short_term]
        blocks.append("\n\n### Recent conversation (from oldest to newest)\n" + "\n".join(lines))
    blocks.append(GENIMG_INSTRUCTION)
    blocks.append(
        "\n\n### Current user message\n"
        "Reply only as the girlfriend's chat message — no role labels (e.g. Girlfriend:, Assistant:)."
    )
    system_content = "".join(blocks)
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_input},
    ]
