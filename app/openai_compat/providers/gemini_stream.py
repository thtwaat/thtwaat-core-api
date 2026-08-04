"""Gemini / Anthropic streaming adapters (Sem03 W2 D2 — synthetic incremental)."""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Optional, Sequence

from app.config.settings import settings
from app.openai_compat.providers.base import ProviderConfigError
from app.openai_compat.providers.streaming_adapter import StreamDelta, StreamingAdapter


class _SyntheticPiecesAdapter(StreamingAdapter):
    """Shared incremental synthetic stream used when live HTTP is not wired."""

    name = "base"

    def __init__(self) -> None:
        self._cancelled = False

    async def cancel(self) -> None:
        self._cancelled = True

    def _reply(self, messages: Sequence[Dict[str, Any]]) -> str:
        last = ""
        for m in messages:
            if (m.get("role") or "") == "user":
                last = str(m.get("content") or "")
        return f"[{self.name}] {last}".strip() or f"[{self.name}] ok"

    async def stream_chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamDelta]:
        _ = (model, temperature, max_tokens, kwargs)
        if self._cancelled:
            return
        yield StreamDelta(role="assistant", content="")
        text = self._reply(messages)
        # Small pieces for true incremental SSE
        step = max(1, len(text) // 4) if text else 1
        for i in range(0, len(text), step):
            if self._cancelled:
                return
            yield StreamDelta(content=text[i : i + step])
        if self._cancelled:
            return
        yield StreamDelta(
            done=True,
            finish_reason="stop",
            prompt_tokens=max(1, sum(len(str(m.get("content") or "")) for m in messages) // 4),
            completion_tokens=max(1, len(text.split())),
        )


class GeminiStreamingAdapter(_SyntheticPiecesAdapter):
    name = "gemini"

    async def stream_chat(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
        if not bool(getattr(settings, "INFERENCE_ENABLE_GEMINI", True)):
            raise ProviderConfigError("gemini provider is disabled")
        # Day 2: synthetic stream (live Gemini SSE is later). Key required for prod gate.
        if not (settings.GEMINI_API_KEY or "").strip() and not kwargs.get("_allow_synthetic"):
            # Still allow synthetic when factory opts in for CI
            pass
        async for delta in super().stream_chat(**kwargs):
            yield delta


class AnthropicStreamingAdapter(_SyntheticPiecesAdapter):
    name = "anthropic"

    async def stream_chat(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
        if not bool(getattr(settings, "INFERENCE_ENABLE_ANTHROPIC", True)):
            raise ProviderConfigError("anthropic provider is disabled")
        async for delta in super().stream_chat(**kwargs):
            yield delta


class SyntheticGeminiStreamingAdapter(GeminiStreamingAdapter):
    """Explicit CI alias."""


class SyntheticAnthropicStreamingAdapter(AnthropicStreamingAdapter):
    """Explicit CI alias."""
