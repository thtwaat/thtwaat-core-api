"""Abstract base class for image-generation providers — mirrors
``app/agent_platform/voice/providers/base.py`` (STTProvider/TTSProvider):
one abstract method, a unified request/result DTO, self-registration into a
name-keyed registry.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.agent_platform.image_generation.schemas import ImageGenerationResult


class ImageGenerationProvider(ABC):
    """Text prompt in, generated image(s) out."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
    ) -> List[ImageGenerationResult]:
        """Generate ``n`` image(s) for ``prompt``."""
        ...
