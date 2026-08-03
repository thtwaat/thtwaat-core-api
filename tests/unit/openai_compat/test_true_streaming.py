"""Semester 03 Week 2 Day 1 — true streaming engine tests."""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Optional, Sequence

import pytest
from fastapi import HTTPException

from app.openai_compat.providers.base import ProviderTimeoutError, ProviderUpstreamError
from app.openai_compat.providers.openai_stream import SyntheticOpenAIStreamingAdapter
from app.openai_compat.providers.stream_metrics import reset_streaming_metrics_for_tests
from app.openai_compat.providers.streaming_adapter import StreamDelta, StreamingAdapter
from app.openai_compat.stream_engine import StreamEngine


class _ScriptedAdapter(StreamingAdapter):
    name = "scripted"

    def __init__(self, deltas: list[StreamDelta], *, fail: Exception | None = None) -> None:
        self._deltas = deltas
        self._fail = fail
        self.cancelled = False

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
        if self._fail is not None:
            raise self._fail
        for d in self._deltas:
            if self.cancelled:
                return
            yield d


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset_streaming_metrics_for_tests()
    yield
    reset_streaming_metrics_for_tests()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_streaming_success_emits_chunks_and_done(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_ENABLED", True, raising=False
    )
    adapter = _ScriptedAdapter(
        [
            StreamDelta(role="assistant", content=""),
            StreamDelta(content="Hello"),
            StreamDelta(content=" world"),
            StreamDelta(
                done=True,
                finish_reason="stop",
                prompt_tokens=2,
                completion_tokens=2,
            ),
        ]
    )
    engine = StreamEngine(adapter=adapter)
    frames = []
    async for frame in engine.aiter_sse(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        provider_name="openai",
    ):
        frames.append(frame)
    assert frames[-1] == "data: [DONE]\n\n"
    joined = "".join(frames)
    assert "Hello" in joined
    assert " world" in joined
    assert engine.result is not None
    assert engine.result.content == "Hello world"
    assert engine.result.cancelled is False
    assert engine.result.metrics is not None
    assert engine.result.metrics.first_token_latency_ms is not None
    assert engine.result.metrics.total_stream_duration_ms >= 0
    assert engine.result.metrics.streamed_tokens >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_client_disconnect_cancels_adapter(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_ENABLED", True, raising=False
    )
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
            # disconnect after first content check following role
            return self.n >= 3

    engine = StreamEngine(adapter=adapter)
    frames = []
    async for frame in engine.aiter_sse(
        model="m",
        messages=[{"role": "user", "content": "x"}],
        provider_name="openai",
        request=_Req(),  # type: ignore[arg-type]
    ):
        frames.append(frame)
    assert adapter.cancelled is True
    assert engine.result is not None
    assert engine.result.cancelled is True
    assert not any(f == "data: [DONE]\n\n" for f in frames)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_stream_still_done(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_ENABLED", True, raising=False
    )
    adapter = _ScriptedAdapter(
        [
            StreamDelta(role="assistant", content=""),
            StreamDelta(done=True, finish_reason="stop", prompt_tokens=1, completion_tokens=0),
        ]
    )
    engine = StreamEngine(adapter=adapter)
    frames = []
    async for frame in engine.aiter_sse(
        model="m",
        messages=[{"role": "user", "content": ""}],
        provider_name="openai",
    ):
        frames.append(frame)
    assert frames[-1] == "data: [DONE]\n\n"
    assert engine.result is not None
    assert engine.result.content == ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_failure_before_bytes(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_ENABLED", True, raising=False
    )
    adapter = _ScriptedAdapter([], fail=ProviderUpstreamError("boom", provider="ollama"))
    engine = StreamEngine(adapter=adapter)
    with pytest.raises(HTTPException) as exc:
        async for _ in engine.aiter_sse(
            model="llama3.2",
            messages=[{"role": "user", "content": "x"}],
            provider_name="ollama",
        ):
            pass
    assert exc.value.status_code == 502
    assert exc.value.detail["error"]["code"] == "upstream_error"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_timeout_maps_to_504(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_ENABLED", True, raising=False
    )
    adapter = _ScriptedAdapter(
        [], fail=ProviderTimeoutError("slow", provider="ollama")
    )
    engine = StreamEngine(adapter=adapter)
    with pytest.raises(HTTPException) as exc:
        async for _ in engine.aiter_sse(
            model="llama3.2",
            messages=[{"role": "user", "content": "x"}],
            provider_name="ollama",
        ):
            pass
    assert exc.value.status_code == 504
    assert exc.value.detail["error"]["code"] == "upstream_timeout"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_disabled(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_ENABLED", False, raising=False
    )
    engine = StreamEngine(adapter=_ScriptedAdapter([]))
    with pytest.raises(HTTPException) as exc:
        async for _ in engine.aiter_sse(
            model="m",
            messages=[{"role": "user", "content": "x"}],
            provider_name="openai",
        ):
            pass
    assert exc.value.detail["error"]["code"] == "stream_disabled"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthetic_openai_adapter_streams():
    adapter = SyntheticOpenAIStreamingAdapter()
    parts = []
    async for d in adapter.stream_chat(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "ping"}],
    ):
        if d.content:
            parts.append(d.content)
    assert "".join(parts).startswith("[openai]")
