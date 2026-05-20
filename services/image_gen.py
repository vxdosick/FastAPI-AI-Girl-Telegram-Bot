# Image generation when the user asks for a picture (OpenRouter, anime-only)
from __future__ import annotations

import base64
import logging
import re
from typing import Any

import httpx
from openai import AsyncOpenAI

from config.config import (
    IMAGE_MODEL,
    IMAGE_SAFETY_PREFIX,
    OPENAI_API_KEY,
    OPENROUTER_BASE_URL,
)

log = logging.getLogger(__name__)

IMAGE_PROMPT_TAG = re.compile(r"^IMAGE_PROMPT:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

IMAGE_INSTRUCTIONS = (
    "\n\n---\nAnime image requests (when he asks for a photo, picture, selfie, or drawing):\n"
    "- Your visible reply stays a normal short girlfriend message in his language.\n"
    "- If you will send a picture, add ONE final line only, exactly: IMAGE_PROMPT: <single-line English prompt>\n"
    "- IMAGE_PROMPT must request ANIME ART ONLY (Japanese anime style illustration) — never photorealistic, "
    "never 3D, never western cartoon.\n"
    "- Subjects: ONLY an adult anime woman (you) and/or an adult anime man in a romantic/flirty scene. "
    "No animals alone, landscapes without characters, logos, memes, crowds, children, celebrities by name.\n"
    "- Clothing (mandatory): fully clothed or tastefully covered — no nudity, no bare breasts/nipples, "
    "no genitals, no explicit poses. Suggestive-but-SFW outfits only.\n"
    "- Forbidden: anyone under 18, childlike/loli/shota faces, drugs, weapons, blood, violence, hate, illegal acts.\n"
    "- If his request breaks rules, refuse sweetly, do NOT output IMAGE_PROMPT, suggest a safe anime alternative "
    "(e.g. cozy anime selfie in sweater, date-night dress, soft hug illustration).\n"
)

_IMAGE_KEYWORDS = (
    "photo", "picture", "pic", "image", "selfie", "draw", "paint", "sketch", "snapshot",
    "send me a", "show me", "see you", "your face", "what you look",
    "фото", "картин", "нарисуй", "рисун", "селфи", "покажи", "изображен",
)


def user_likely_wants_image(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _IMAGE_KEYWORDS)


def fallback_image_prompt_from_user(user_text: str) -> str:
    snippet = (user_text or "").strip()[:300]
    return (
        f"Anime illustration, romantic adult girlfriend selfie inspired by: {snippet}. "
        "Adult anime woman, fully clothed, soft lighting, flirty SFW mood."
    )


def wrap_anime_image_prompt(prompt: str) -> str:
    return f"{IMAGE_SAFETY_PREFIX} {prompt}".strip()


def split_reply_and_image_prompt(reply: str) -> tuple[str, str | None]:
    text = (reply or "").strip()
    match = IMAGE_PROMPT_TAG.search(text)
    if not match:
        return text, None
    prompt = match.group(1).strip()
    visible = IMAGE_PROMPT_TAG.sub("", text).strip()
    return visible, prompt or None


def _decode_data_url(url: str) -> bytes | None:
    if not url or not url.startswith("data:"):
        return None
    try:
        payload = url.split(",", 1)[-1]
        return base64.b64decode(payload)
    except Exception:
        return None


async def _fetch_url_bytes(url: str) -> bytes | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content
    except Exception:
        log.exception("Failed to download image url")
        return None


def _url_from_image_obj(img: Any) -> str | None:
    if isinstance(img, dict):
        if "url" in img and img["url"]:
            return str(img["url"])
        iu = img.get("image_url")
        if isinstance(iu, dict) and iu.get("url"):
            return str(iu["url"])
        if isinstance(iu, str):
            return iu
    url = getattr(img, "url", None)
    if url:
        return str(url)
    iu = getattr(img, "image_url", None)
    if isinstance(iu, dict) and iu.get("url"):
        return str(iu["url"])
    return None


async def _bytes_from_url(url: str) -> bytes | None:
    if url.startswith("data:"):
        return _decode_data_url(url)
    return await _fetch_url_bytes(url)


async def extract_image_bytes_from_completion(completion: Any) -> bytes | None:
    choices = getattr(completion, "choices", None) if completion else None
    if not choices:
        return None
    msg = choices[0].message

    images = getattr(msg, "images", None) or []
    for img in images:
        url = _url_from_image_obj(img)
        if not url:
            continue
        data = await _bytes_from_url(url)
        if data:
            return data

    content = getattr(msg, "content", None)
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url")
                if url:
                    data = await _bytes_from_url(url)
                    if data:
                        return data
    return None


async def _generate_via_modalities(client: AsyncOpenAI, model: str, prompt: str) -> bytes | None:
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        extra_body={
            "modalities": ["image", "text"],
            "image_config": {
                "aspect_ratio": "1:1",
                "image_size": "1K",
            },
        },
    )
    return await extract_image_bytes_from_completion(resp)


async def generate_image(prompt: str) -> bytes | None:
    model = (IMAGE_MODEL or "").strip()
    if not model:
        log.warning("IMAGE_MODEL not set — skipping image generation")
        return None

    safe_prompt = wrap_anime_image_prompt(prompt)
    client = AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENAI_API_KEY)

    try:
        data = await _generate_via_modalities(client, model, safe_prompt)
        if data:
            return data
    except Exception:
        log.exception("Anime image generation failed for model=%s", model)

    return None
