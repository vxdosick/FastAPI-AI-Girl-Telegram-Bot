# Safe parsing of OpenRouter / OpenAI chat completion responses
from __future__ import annotations

from typing import Any


def extract_assistant_text(completion: Any) -> str | None:
    """
    Return assistant message text.
    None means the response has no choices (API anomaly or blocked response).
    """
    if completion is None:
        return None
    choices = getattr(completion, "choices", None)
    if not choices:
        return None

    message = getattr(choices[0], "message", None)
    if message is None:
        return None

    content = getattr(message, "content", None)
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)

    return str(content)
