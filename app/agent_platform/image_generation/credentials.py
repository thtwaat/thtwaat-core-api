"""Image-generation provider credential resolution — mirrors
``app/agent_platform/voice/credentials.py``: global, platform-level keys
from settings today (same shortcut the LLM gateway and voice module take),
not a per-company DB row.
"""
from __future__ import annotations

from typing import Optional

from app.config.settings import settings


def resolve_image_generation_api_key(provider_name: str) -> Optional[str]:
    key_map = {
        "openai": settings.OPENAI_API_KEY,
    }
    return key_map.get((provider_name or "").lower())
