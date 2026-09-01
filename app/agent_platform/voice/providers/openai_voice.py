"""OpenAI STT (Whisper) + TTS adapters — the only registered voice providers
today. Mirrors app/agent_platform/providers/openai.py: lazily builds an
AsyncOpenAI client from the resolved api_key and self-registers on import.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.agent_platform.voice.providers.base import STTProvider, TTSProvider
from app.agent_platform.voice.registries import STTProviderRegistry, TTSProviderRegistry
from app.agent_platform.voice.schemas import STTResult, TTSResult

logger = logging.getLogger(__name__)

_STT_MODEL = "whisper-1"
_TTS_MODEL = "tts-1"

# Whisper needs a filename with a recognized extension to infer the container
# format — map common browser/telephony MIME types to one.
_MIME_TO_EXT = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
}


def _extension_for(mime_type: str) -> str:
    return _MIME_TO_EXT.get((mime_type or "").lower().split(";")[0].strip(), "wav")


class OpenAISTTProvider(STTProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured — voice/STT unavailable.")
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        mime_type: str,
        language: Optional[str] = None,
    ) -> STTResult:
        client = self._get_client()
        filename = f"audio.{_extension_for(mime_type)}"
        kwargs = {
            "model": _STT_MODEL,
            "file": (filename, audio_bytes, mime_type or "audio/wav"),
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language
        response = await client.audio.transcriptions.create(**kwargs)
        return STTResult(
            text=(getattr(response, "text", None) or "").strip(),
            language=getattr(response, "language", None) or language,
            duration_seconds=float(getattr(response, "duration", 0.0) or 0.0),
            provider="openai",
            model=_STT_MODEL,
        )


class OpenAITTSProvider(TTSProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured — voice/TTS unavailable.")
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str,
        language: Optional[str] = None,
        speed: float = 1.0,
    ) -> TTSResult:
        client = self._get_client()
        # OpenAI TTS speed is clamped to [0.25, 4.0].
        clamped_speed = max(0.25, min(4.0, float(speed or 1.0)))
        response = await client.audio.speech.create(
            model=_TTS_MODEL,
            voice=voice_id or "alloy",
            input=text,
            speed=clamped_speed,
            response_format="mp3",
        )
        audio_bytes = response.content if hasattr(response, "content") else bytes(response)
        # No duration returned by the API — estimate from a typical TTS
        # speaking rate (~150 wpm at 1.0x) so usage tracking has a value.
        word_count = max(1, len(text.split()))
        estimated_duration = (word_count / 150.0) * 60.0 / clamped_speed
        return TTSResult(
            audio_bytes=audio_bytes,
            mime_type="audio/mpeg",
            duration_seconds=estimated_duration,
            provider="openai",
            model=_TTS_MODEL,
        )


STTProviderRegistry.register("openai", OpenAISTTProvider)
TTSProviderRegistry.register("openai", OpenAITTSProvider)
