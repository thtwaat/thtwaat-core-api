"""Semester 03 Week 2 Day 2 — production streaming reliability."""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, Optional, Sequence

import pytest
from fastapi import HTTPException

from app.openai_compat.providers.base import ProviderTimeoutError, ProviderUpstreamError
from app.openai_compat.providers.stream_metrics import (
    get_streaming_metrics,
    reset_streaming_metrics_for_tests,
)
from app.openai_compat.providers.streaming_adapter import StreamDelta, StreamingAdapter
from app.openai_compat.stream_engine import StreamEngine, StreamPreTokenError
from app.openai_compat.stream_routing import (
    normalize_stream_provider,
    resolve_stream_provider_chain,
    stream_fallback_order,
)


class _ScriptedAdapter(StreamingAdapter):
    name = "scripted"

    def __init__(
        self,
        deltas: list[StreamDelta],
        *,
        fail: Exception | None = None,
        delay: float = 0.0,
        fail_after: int | None = None,
    ) -> None:
        self._deltas = deltas
        self._fail = fail
        self._delay = delay
        self._fail_after = fail_after
        self.cancelled = False
        self.started = False

    async def cancel(self) -> None:
        self.cancelled = True

    async def stream_chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamDelta]:
        self.started = True
        if self._fail is not None and self._fail_after is None:
            raise self._fail
        for i, d in enumerate(self._deltas):
            if self.cancelled:
                return
            if self._delay:
                await asyncio.sleep(self._delay)
            if self._fail is not None and self._fail_after is not None and i >= self._fail_after:
                raise self._fail
            yield d


class _NamedFailAdapter(StreamingAdapter):
    def __init__(self, name: str, *, fail: Exception | None = None, text: str = "ok") -> None:
        self.name = name
        self._fail = fail
        self._text = text
        self.cancelled = False
        self.calls = 0

    async def cancel(self) -> None:
        self.cancelled = True

    async def stream_chat(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
        self.calls += 1
        if self._fail is not None:
            raise self._fail
        yield StreamDelta(role="assistant", content="")
        yield StreamDelta(content=self._text)
        yield StreamDelta(done=True, finish_reason="stop", completion_tokens=1)


@pytest.fixture(autouse=True)
def _reset_metrics(monkeypatch):
    monkeypatch.setattr("app.config.settings.settings.STREAM_ENABLED", True, raising=False)
    monkeypatch.setattr("app.config.settings.settings.STREAM_CONNECT_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr("app.config.settings.settings.STREAM_FIRST_TOKEN_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr("app.config.settings.settings.STREAM_IDLE_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr("app.config.settings.settings.STREAM_MAX_QUEUED_EVENTS", 64, raising=False)
    reset_streaming_metrics_for_tests()
    yield
    reset_streaming_metrics_for_tests()


@pytest.mark.unit
def test_provider_routing_policies_default_auto():
    assert normalize_stream_provider(None) == "auto"
    assert normalize_stream_provider("") == "auto"
    assert normalize_stream_provider("OLLAMA") == "ollama"
    assert normalize_stream_provider("openai") == "openai"
    assert normalize_stream_provider("gemini") == "gemini"
    assert normalize_stream_provider("anthropic") == "anthropic"
    with pytest.raises(HTTPException):
        normalize_stream_provider("vllm")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fallback_order_explicit_provider_first(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_FALLBACK_ORDER",
        "ollama,openai,gemini,anthropic",
        raising=False,
    )
    chain = await resolve_stream_provider_chain(model="gpt-4o-mini", provider="openai")
    assert chain[0] == "openai"
    assert "ollama" in chain
    assert chain == stream_fallback_order() or chain[0] == "openai"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_streaming_success_day2_metrics(monkeypatch):
    adapter = _ScriptedAdapter(
        [
            StreamDelta(role="assistant", content=""),
            StreamDelta(content="Hello"),
            StreamDelta(done=True, finish_reason="stop", completion_tokens=1),
        ]
    )
    engine = StreamEngine(adapter=adapter)
    frames = [f async for f in engine.aiter_sse(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        provider_name="openai",
        request_id="req-1",
        tenant_id="tenant-1",
    )]
    assert frames[-1] == "data: [DONE]\n\n"
    snap = get_streaming_metrics().snapshot()
    assert snap["stream_started"] >= 1
    assert snap["stream_completed"] >= 1
    assert snap["tokens_streamed"] >= 1
    assert engine.result is not None
    assert engine.result.metrics is not None
    assert engine.result.metrics.provider_latency_ms is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fallback_before_first_token(monkeypatch):
    primary = _NamedFailAdapter("ollama", fail=ProviderUpstreamError("down"))
    secondary = _NamedFailAdapter("openai", text="recovered")

    def _factory(name: str):
        if name == "ollama":
            return primary
        if name == "openai":
            return secondary
        raise AssertionError(name)

    monkeypatch.setattr(
        "app.openai_compat.stream_engine.get_streaming_adapter", _factory
    )
    engine = StreamEngine()
    frames = [
        f
        async for f in engine.aiter_sse(
            model="m",
            messages=[{"role": "user", "content": "x"}],
            provider_chain=["ollama", "openai"],
        )
    ]
    joined = "".join(frames)
    assert "recovered" in joined
    assert primary.calls == 1
    assert secondary.calls == 1
    assert engine.result is not None
    assert engine.result.provider == "openai"
    assert engine.result.fallback_used is True
    assert get_streaming_metrics().snapshot()["fallback_used"] >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_fallback_after_stream_started(monkeypatch):
    """Once SSE frames are out, provider errors must not switch providers."""
    boom = ProviderUpstreamError("mid-stream")
    primary = _ScriptedAdapter(
        [
            StreamDelta(role="assistant", content=""),
            StreamDelta(content="partial"),
        ],
        fail=boom,
        fail_after=2,
    )
    secondary = _NamedFailAdapter("openai", text="should-not-run")

    def _factory(name: str):
        if name == "ollama":
            return primary
        return secondary

    monkeypatch.setattr(
        "app.openai_compat.stream_engine.get_streaming_adapter", _factory
    )
    engine = StreamEngine()
    frames = [
        f
        async for f in engine.aiter_sse(
            model="m",
            messages=[{"role": "user", "content": "x"}],
            provider_chain=["ollama", "openai"],
        )
    ]
    joined = "".join(frames)
    assert "partial" in joined
    assert "should-not-run" not in joined
    assert secondary.calls == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_first_token_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_FIRST_TOKEN_TIMEOUT", 0.05, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_CONNECT_TIMEOUT", 0.05, raising=False
    )
    adapter = _ScriptedAdapter(
        [StreamDelta(role="assistant", content=""), StreamDelta(content="late")],
        delay=0.2,
    )
    engine = StreamEngine(adapter=adapter)
    with pytest.raises(HTTPException) as ei:
        async for _ in engine.aiter_sse(
            model="m",
            messages=[{"role": "user", "content": "x"}],
            provider_name="openai",
        ):
            pass
    assert ei.value.status_code in (504, 502, 500)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancellation_on_disconnect(monkeypatch):
    adapter = _ScriptedAdapter(
        [
            StreamDelta(role="assistant", content=""),
            StreamDelta(content="one"),
            StreamDelta(content="two"),
            StreamDelta(done=True, finish_reason="stop", completion_tokens=2),
        ]
    )

    class _Req:
        def __init__(self):
            self.n = 0

        async def is_disconnected(self) -> bool:
            self.n += 1
            return self.n >= 2

    engine = StreamEngine(adapter=adapter)
    async for _ in engine.aiter_sse(
        model="m",
        messages=[{"role": "user", "content": "x"}],
        provider_name="openai",
        request=_Req(),
    ):
        pass
    assert adapter.cancelled is True
    assert engine.result is not None
    assert engine.result.cancelled is True
    assert get_streaming_metrics().snapshot()["stream_cancelled"] >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_slow_client_backpressure_disconnect(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_MAX_QUEUED_EVENTS", 1, raising=False
    )

    class _FloodAdapter(StreamingAdapter):
        name = "flood"

        def __init__(self) -> None:
            self.cancelled = False

        async def cancel(self) -> None:
            self.cancelled = True

        async def stream_chat(self, **kwargs: Any) -> AsyncIterator[StreamDelta]:
            yield StreamDelta(role="assistant", content="")
            for i in range(50):
                if self.cancelled:
                    return
                yield StreamDelta(content=f"t{i} ")
                await asyncio.sleep(0.001)
            yield StreamDelta(done=True, finish_reason="stop")

    class _SlowReq:
        async def is_disconnected(self) -> bool:
            return True

    adapter = _FloodAdapter()
    engine = StreamEngine(adapter=adapter)
    # Consumer that stalls — producer fills queue; disconnect flips cancel path
    frames = []
    async for frame in engine.aiter_sse(
        model="m",
        messages=[{"role": "user", "content": "x"}],
        request=_SlowReq(),
    ):
        frames.append(frame)
        await asyncio.sleep(0.01)
    assert adapter.cancelled is True or (engine.result and engine.result.cancelled)
