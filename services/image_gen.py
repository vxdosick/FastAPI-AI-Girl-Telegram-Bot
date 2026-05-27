# Image generation for genimg commands (OpenRouter, anime-only)
from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from config.config import (
    IMAGES_AI_MODEL,
    IMAGE_SAFETY_PREFIX,
    OPENAI_API_KEY,
    OPENROUTER_BASE_URL,
)

log = logging.getLogger(__name__)

_MODALITY_ATTEMPTS = (["image", "text"], ["image"])

_IMAGE_DIRECTIVE = (
    "Generate ONE anime image. Output must include an image — never reply with refusal text only. "
    "If the scene is very explicit, translate it into the most flirtatious adult anime picture you can "
    "still render: suggestive pose, bedroom lighting, blushing, tight or revealing-but-covered outfit, "
    "maximum tease on the SFW boundary — slightly less explicit than requested is OK, empty output is NOT."
)


def _fallback_tease_prompt(user_prompt: str) -> str:
    snippet = (user_prompt or "").strip()[:220]
    return (
        "Adult anime girlfriend, sultry romantic selfie or intimate date-night scene, "
        "flirty shy-bold expression, warm soft lighting, suggestive mood but fully covered, "
        "lingerie or tight dress, maximum tease within SFW rules. "
        f"Inspired by: {snippet}"
    )


def wrap_anime_image_prompt(prompt: str) -> str:
    user_scene = (prompt or "").strip()
    return f"{IMAGE_SAFETY_PREFIX} {_IMAGE_DIRECTIVE} User request: {user_scene}".strip()


def _chat_completions_url() -> str:
    base = (OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1").rstrip("/")
    return f"{base}/chat/completions"


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
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except Exception:
        log.exception("Failed to download image url")
        return None


async def _bytes_from_url(url: str) -> bytes | None:
    if url.startswith("data:"):
        return _decode_data_url(url)
    return await _fetch_url_bytes(url)


def _url_from_image_obj(img: Any) -> str | None:
    if isinstance(img, dict):
        image_url = img.get("image_url")
        if isinstance(image_url, dict) and image_url.get("url"):
            return str(image_url["url"])
        if isinstance(image_url, str):
            return image_url
        if img.get("url"):
            return str(img["url"])
    image_url = getattr(img, "image_url", None)
    if isinstance(image_url, dict) and image_url.get("url"):
        return str(image_url["url"])
    url = getattr(img, "url", None)
    return str(url) if url else None


async def extract_image_bytes_from_message(message: dict[str, Any]) -> bytes | None:
    for img in message.get("images") or []:
        url = _url_from_image_obj(img)
        if not url:
            continue
        data = await _bytes_from_url(url)
        if data:
            return data

    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            url = (part.get("image_url") or {}).get("url")
            if url:
                data = await _bytes_from_url(str(url))
                if data:
                    return data
    return None


def _is_modality_mismatch(status_code: int, body: str) -> bool:
    if status_code != 404:
        return False
    lowered = body.lower()
    return "modalities" in lowered or "output modalities" in lowered


async def _request_openrouter_image(model: str, prompt: str) -> bytes | None:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    base_payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if "gemini" in model.lower():
        base_payload["image_config"] = {
            "aspect_ratio": "1:1",
            "image_size": "1K",
        }

    async with httpx.AsyncClient(timeout=120.0) as client:
        for modalities in _MODALITY_ATTEMPTS:
            payload = {**base_payload, "modalities": modalities}
            response = await client.post(
                _chat_completions_url(),
                headers=headers,
                json=payload,
            )
            body = response.text

            if _is_modality_mismatch(response.status_code, body):
                log.info(
                    "Retrying image generation with modalities=%s for model=%s",
                    modalities,
                    model,
                )
                continue

            if response.status_code >= 400:
                log.error(
                    "OpenRouter image request failed model=%s status=%s body=%s",
                    model,
                    response.status_code,
                    body[:500],
                )
                return None

            try:
                data = response.json()
            except ValueError:
                log.exception("OpenRouter returned non-JSON response for model=%s", model)
                return None

            choices = data.get("choices") or []
            if not choices:
                log.warning("OpenRouter image response had no choices for model=%s", model)
                return None

            message = choices[0].get("message") or {}
            image_bytes = await extract_image_bytes_from_message(message)
            if image_bytes:
                return image_bytes

            log.warning(
                "OpenRouter image response had no image payload for model=%s modalities=%s",
                model,
                modalities,
            )

    return None


async def generate_image(prompt: str) -> bytes | None:
    model = (IMAGES_AI_MODEL or "").strip()
    if not model:
        log.warning("IMAGES_AI_MODEL not set — skipping image generation")
        return None

    prompt_attempts = [
        wrap_anime_image_prompt(prompt),
        wrap_anime_image_prompt(_fallback_tease_prompt(prompt)),
    ]

    try:
        for idx, safe_prompt in enumerate(prompt_attempts):
            data = await _request_openrouter_image(model, safe_prompt)
            if data:
                if idx > 0:
                    log.info("Image generated via tease fallback")
                return data
    except Exception:
        log.exception("Anime image generation failed for model=%s", model)

    return None
