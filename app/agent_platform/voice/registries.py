"""Name-keyed registries for STT/TTS providers — mirrors
``app/agent_platform/registries/provider_registry.py``."""
from __future__ import annotations

from typing import Dict, Type

from app.agent_platform.voice.providers.base import STTProvider, TTSProvider


class STTProviderRegistry:
    _providers: Dict[str, Type[STTProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[STTProvider]) -> None:
        cls._providers[name] = provider_class

    @classmethod
    def get_provider(cls, name: str, api_key: str) -> STTProvider:
        provider_class = cls._providers.get(name)
        if not provider_class:
            raise ValueError(f"STT provider '{name}' is not registered.")
        return provider_class(api_key=api_key)


class TTSProviderRegistry:
    _providers: Dict[str, Type[TTSProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[TTSProvider]) -> None:
        cls._providers[name] = provider_class

    @classmethod
    def get_provider(cls, name: str, api_key: str) -> TTSProvider:
        provider_class = cls._providers.get(name)
        if not provider_class:
            raise ValueError(f"TTS provider '{name}' is not registered.")
        return provider_class(api_key=api_key)
