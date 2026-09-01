"""Abstract base classes for speech providers — mirrors
``app/agent_platform/providers/base.py`` (LLMProvider): one abstract method,
a unified request/response DTO, self-registration into a name-keyed registry.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.agent_platform.voice.schemas import STTResult, TTSResult


class STTProvider(ABC):
    """Speech-to-text: raw audio bytes in, transcript out."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        mime_type: str,
        language: Optional[str] = None,
    ) -> STTResult:
        """Transcribe ``audio_bytes`` (already in a provider-supported container
        format, e.g. wav/mp3/webm/m4a) to text."""
        ...


class TTSProvider(ABC):
    """Text-to-speech: text in, raw audio bytes out."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str,
        language: Optional[str] = None,
        speed: float = 1.0,
    ) -> TTSResult:
        """Synthesize ``text`` into speech audio."""
        ...
