"""Resolve StreamingAdapter by provider name (Sem03 W2 D1)."""
from __future__ import annotations

from typing import Optional

from app.config.settings import settings
from app.openai_compat.providers.base import ProviderNotFoundError
from app.openai_compat.providers.ollama_stream import OllamaStreamingAdapter
from app.openai_compat.providers.openai_stream import (
    OpenAIStreamingAdapter,
    SyntheticOpenAIStreamingAdapter,
)
from app.openai_compat.providers.streaming_adapter import StreamingAdapter


def get_streaming_adapter(provider_name: str) -> StreamingAdapter:
    name = (provider_name or "").strip().lower()
    if name == "ollama":
        return OllamaStreamingAdapter()
    if name == "openai":
        if (settings.OPENAI_API_KEY or "").strip() and bool(
            getattr(settings, "INFERENCE_STREAM_LIVE_OPENAI", True)
        ):
            return OpenAIStreamingAdapter()
        return SyntheticOpenAIStreamingAdapter()
    raise ProviderNotFoundError(
        f"Streaming is not implemented for provider '{provider_name}' on Day 1 "
        f"(supported: ollama, openai)"
    )


def stream_enabled() -> bool:
    return bool(getattr(settings, "STREAM_ENABLED", True))
