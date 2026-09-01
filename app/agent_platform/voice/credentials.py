"""Voice provider credential resolution — mirrors
``app/agent_platform/gateway/resolvers.py::get_provider_config``: global,
platform-level keys from settings today (same shortcut the LLM gateway takes),
not a per-company DB row. Centralized here so wiring a per-company
``ProviderConfig`` lookup later touches one function, not every call site.
"""
from __future__ import annotations

from typing import Optional

from app.config.settings import settings


def resolve_voice_api_key(provider_name: str) -> Optional[str]:
    key_map = {
        "openai": settings.OPENAI_API_KEY,
    }
    return key_map.get((provider_name or "").lower())
