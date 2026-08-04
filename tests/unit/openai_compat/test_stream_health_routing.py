"""Semester 03 Week 2 Day 3 — health-aware stream routing."""
from __future__ import annotations

from typing import Any, AsyncIterator

import pytest
from fastapi import HTTPException

from app.openai_compat.inference_routing_repository import ProviderProfile
from app.openai_compat.providers.base import ProviderUpstreamError
from app.openai_compat.providers.capabilities import ProviderCapability
from app.openai_compat.providers.health_cache import (
    get_health_cache,
    reset_health_cache_for_tests,
)
from app.openai_compat.providers.inference_router import InferenceRouter
from app.openai_compat.providers.stream_metrics import (
    get_streaming_metrics,
    reset_streaming_metrics_for_tests,
)
from app.openai_compat.providers.streaming_adapter import StreamDelta, StreamingAdapter
from app.openai_compat.stream_engine import StreamEngine
from app.openai_compat.stream_routing import (
    StreamProviderChain,
    filter_healthy_stream_providers,
    resolve_stream_provider_chain,
)


class _NamedAdapter(StreamingAdapter):
    def __init__(self, name: str, *, fail: Exception | None = None, text: str = "ok") -> None:
        self.name = name
        self._fail = fail
        self._text = text
        self.calls = 0
        self.cancelled = False

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
def _reset(monkeypatch):
    monkeypatch.setattr("app.config.settings.settings.STREAM_ENABLED", True, raising=False)
    monkeypatch.setattr(
        "app.config.settings.settings.STREAM_FALLBACK_ORDER",
        "ollama,openai,gemini,anthropic",
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_HEALTH_CACHE_TTL_SECONDS",
        60.0,
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ROUTING_POLICY",
        "default",
        raising=False,
    )
    reset_streaming_metrics_for_tests()
    reset_health_cache_for_tests(ttl_seconds=60.0)
    yield
    reset_streaming_metrics_for_tests()
    reset_health_cache_for_tests()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unhealthy_primary_skipped_next_healthy_used(monkeypatch):
    get_health_cache().put("ollama", {"ok": False, "error": "down"})

    async def _filter(names, **kwargs):
        healthy, skipped = [], []
        for n in names:
            cached = get_health_cache().get_cached(n)
            if cached is not None and not cached.get("ok"):
                skipped.append(n)
            else:
                healthy.append(n)
        return healthy, skipped

    monkeypatch.setattr(
        "app.openai_compat.stream_routing.filter_healthy_stream_providers",
        _filter,
    )
    monkeypatch.setattr(
        "app.openai_compat.stream_routing._stream_pool_for_model",
        lambda model, router: ["ollama", "openai", "gemini"],
    )

    chain = await resolve_stream_provider_chain(model="shared", provider="auto")
    assert "ollama" not in chain.providers
    assert chain.providers[0] == "openai"
    assert "ollama" in chain.skipped_unhealthy


@pytest.mark.unit
@pytest.mark.asyncio
async def test_explicit_provider_attempted_even_if_unhealthy(monkeypatch):
    get_health_cache().put("ollama", {"ok": False, "error": "down"})

    async def _filter(names, **kwargs):
        healthy, skipped = [], []
        for n in names:
            cached = get_health_cache().get_cached(n)
            if cached is not None and not cached.get("ok"):
                skipped.append(n)
            else:
                healthy.append(n)
        return healthy, skipped

    monkeypatch.setattr(
        "app.openai_compat.stream_routing.filter_healthy_stream_providers",
        _filter,
    )
    chain = await resolve_stream_provider_chain(model="m", provider="ollama")
    assert chain.providers[0] == "ollama"
    assert "openai" in chain.providers


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pre_token_failure_marks_unhealthy_and_next_chain_omits(monkeypatch):
    primary = _NamedAdapter("ollama", fail=ProviderUpstreamError("boom"))
    secondary = _NamedAdapter("openai", text="fallback-ok")

    def _factory(name: str):
        if name == "ollama":
            return primary
        if name == "openai":
            return secondary
        raise AssertionError(name)

    monkeypatch.setattr("app.openai_compat.stream_engine.get_streaming_adapter", _factory)

    engine = StreamEngine()
    frames = [
        f
        async for f in engine.aiter_sse(
            model="m",
            messages=[{"role": "user", "content": "x"}],
            provider_chain=["ollama", "openai"],
        )
    ]
    assert "fallback-ok" in "".join(frames)
    cached = get_health_cache().get_cached("ollama")
    assert cached is not None
    assert cached.get("ok") is False
    assert get_streaming_metrics().snapshot()["stream_providers_unhealthy"] >= 1

    router = InferenceRouter()

    async def _health(provider) -> bool:
        row = get_health_cache().get_cached(provider.name)
        if row is not None:
            return bool(row.get("ok"))
        return True

    monkeypatch.setattr(router, "is_healthy", _health)
    healthy, skipped = await filter_healthy_stream_providers(
        ["ollama", "openai"], router=router
    )
    assert "ollama" in skipped
    assert "openai" in healthy


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auto_policy_cheapest_orders_before_health_filter(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ROUTING_POLICY",
        "cheapest",
        raising=False,
    )

    class _Repo:
        def get_profile(self, name: str):
            costs = {"openai": 1.0, "ollama": 10.0, "gemini": 5.0, "anthropic": 20.0}
            return ProviderProfile(
                name=name,
                priority=1,
                cost=costs.get(name, 50.0),
                latency_ms=100.0,
                quality=50.0,
                capabilities=frozenset({ProviderCapability.CHAT}),
            )

        def priority_order(self):
            return ["ollama", "openai", "gemini", "anthropic"]

    router = InferenceRouter(repository=_Repo())  # type: ignore[arg-type]
    monkeypatch.setattr(router, "_owners_of_model", lambda _m: ["ollama", "openai", "gemini"])
    monkeypatch.setattr(
        "app.openai_compat.providers.inference_router.InferenceRouter",
        lambda *a, **k: router,
    )

    async def _passthrough(names, router=None, **kwargs):
        return list(names), []

    monkeypatch.setattr(
        "app.openai_compat.stream_routing.filter_healthy_stream_providers",
        _passthrough,
    )

    chain = await resolve_stream_provider_chain(model="shared", provider="auto")
    assert chain.providers[0] == "openai"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_healthy_set_returns_503(monkeypatch):
    async def _none_healthy(names, **kwargs):
        return [], list(names)

    monkeypatch.setattr(
        "app.openai_compat.stream_routing.filter_healthy_stream_providers",
        _none_healthy,
    )
    monkeypatch.setattr(
        "app.openai_compat.stream_routing._stream_pool_for_model",
        lambda model, router: ["ollama", "openai"],
    )
    with pytest.raises(HTTPException) as ei:
        await resolve_stream_provider_chain(model="m", provider="auto")
    assert ei.value.status_code == 503
    assert ei.value.detail["error"]["code"] == "no_healthy_provider"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_skipped_metrics_recorded(monkeypatch):
    resolved = StreamProviderChain(
        providers=["openai"],
        skipped_unhealthy=["ollama", "gemini"],
    )
    adapter = _NamedAdapter("openai", text="hi")

    monkeypatch.setattr(
        "app.openai_compat.stream_engine.get_streaming_adapter",
        lambda name: adapter,
    )
    engine = StreamEngine()
    async for _ in engine.aiter_sse(
        model="m",
        messages=[{"role": "user", "content": "x"}],
        provider_chain=resolved,
    ):
        pass
    snap = get_streaming_metrics().snapshot()
    assert snap["health_skipped"] >= 2
    assert engine.result is not None
    assert engine.result.metrics is not None
    assert engine.result.metrics.health_skipped == 2
