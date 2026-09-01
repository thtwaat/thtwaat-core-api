"""Name-keyed registry for image-generation providers — mirrors
``app/agent_platform/voice/registries.py``."""
from __future__ import annotations

from typing import Dict, Type

from app.agent_platform.image_generation.providers.base import ImageGenerationProvider


class ImageGenerationProviderRegistry:
    _providers: Dict[str, Type[ImageGenerationProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[ImageGenerationProvider]) -> None:
        cls._providers[name] = provider_class

    @classmethod
    def get_provider(cls, name: str, api_key: str) -> ImageGenerationProvider:
        provider_class = cls._providers.get(name)
        if not provider_class:
            raise ValueError(f"Image generation provider '{name}' is not registered.")
        return provider_class(api_key=api_key)
