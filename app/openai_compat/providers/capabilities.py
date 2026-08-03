"""Provider capability detection (Sem03 W1 D3)."""
from __future__ import annotations

from enum import Enum
from typing import Iterable, Set


class ProviderCapability(str, Enum):
    CHAT = "chat"
    EMBEDDINGS = "embeddings"
    IMAGE_GENERATION = "image_generation"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"


def normalize_capabilities(values: Iterable[str | ProviderCapability]) -> Set[ProviderCapability]:
    out: Set[ProviderCapability] = set()
    for raw in values:
        if isinstance(raw, ProviderCapability):
            out.add(raw)
            continue
        key = str(raw or "").strip().lower()
        if not key:
            continue
        out.add(ProviderCapability(key))
    return out


def has_capability(
    owned: Iterable[str | ProviderCapability],
    required: str | ProviderCapability,
) -> bool:
    caps = normalize_capabilities(owned)
    need = (
        required
        if isinstance(required, ProviderCapability)
        else ProviderCapability(str(required).strip().lower())
    )
    return need in caps
