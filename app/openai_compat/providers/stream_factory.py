"""Resolve StreamingAdapter by provider name (Sem03 W2 D1 + D2)."""
from __future__ import annotations

from app.config.settings import settings
from app.openai_compat.providers.base import ProviderNotFoundError
from app.openai_compat.providers.gemini_stream import (
    AnthropicStreamingAdapter,
    GeminiStreamingAdapter,
)
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
    if name == "gemini":
        return GeminiStreamingAdapter()
    if name == "anthropic":
        return AnthropicStreamingAdapter()
    raise ProviderNotFoundError(
        f"Streaming is not implemented for provider '{provider_name}' "
        f"(supported: ollama, openai, gemini, anthropic)"
    )


def stream_enabled() -> bool:
    return bool(getattr(settings, "STREAM_ENABLED", True))
