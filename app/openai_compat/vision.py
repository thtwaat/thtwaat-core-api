"""Vision-ready message content helpers (additive, OpenAI parts format)."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Union


ContentPart = Dict[str, Any]
MessageContent = Union[str, List[ContentPart], None]


def is_vision_content(content: MessageContent) -> bool:
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") in ("image_url", "input_image", "image"):
            return True
    return False


def normalize_message_content(content: MessageContent) -> MessageContent:
    """Pass through OpenAI multimodal parts; stringify unknown shapes safely."""
    if content is None or isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    out: List[ContentPart] = []
    for part in content:
        if isinstance(part, str):
            out.append({"type": "text", "text": part})
            continue
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype == "text" and "text" in part:
            out.append({"type": "text", "text": str(part.get("text") or "")})
        elif ptype in ("image_url", "input_image", "image"):
            image = part.get("image_url") or part.get("image") or {}
            if isinstance(image, str):
                image = {"url": image}
            out.append({"type": "image_url", "image_url": image})
        else:
            out.append(part)
    return out


def flatten_text(content: MessageContent) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    texts: List[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text":
            texts.append(str(part.get("text") or ""))
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(t for t in texts if t)


def messages_require_vision(messages: Sequence[Dict[str, Any]]) -> bool:
    return any(is_vision_content(m.get("content")) for m in messages)
