"""Semester 03 Week 1 Day 3 — InferenceRouter policies & health-aware routing."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.openai_compat.inference_routing_repository import (
    get_routing_repository,
    reset_routing_repository_for_tests,
)
from app.openai_compat.inference_routing_service import InferenceRoutingService
from app.openai_compat.providers import ensure_providers_registered
from app.openai_compat.providers.capabilities import ProviderCapability
from app.openai_compat.providers.health_cache import (
    get_health_cache,
    reset_health_cache_for_tests,
)
from app.openai_compat.providers.inference_router import InferenceRouter
from app.openai_compat.providers.metrics import (
    get_routing_metrics,
    reset_routing_metrics_for_tests,
)
from app.openai_compat.providers.registry import get_registry, reset_registry_for_tests


@pytest.fixture
def fresh_router(monkeypatch):
    reset_registry_for_tests()
    reset_health_cache_for_tests(ttl_seconds=30.0)
    reset_routing_metrics_for_tests()
    reset_routing_repository_for_tests()
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_OLLAMA", True, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_OPENAI", True, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_GEMINI", True, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_ANTHROPIC", True, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_VLLM", False, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_DEFAULT_PROVIDER",
        "ollama",
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_FALLBACK_PROVIDER",
        "openai",
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ROUTING_POLICY",
        "default",
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_HEALTH_CACHE_TTL_SECONDS",
        30,
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.settings.OPENAI_API_KEY", "sk-test", raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.GEMINI_API_KEY", "ge-test", raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.ANTHROPIC_API_KEY", "an-test", raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.OLLAMA_URL",
        "http://127.0.0.1:11434",
        raising=False,
    )
    ensure_providers_registered()

    router = InferenceRouter(
        registry=get_registry(),
        repository=get_routing_repository(),
        health_cache=get_health_cache(),
        metrics=get_routing_metrics(),
    )

    async def _always_healthy(provider) -> bool:
        return True

    monkeypatch.setattr(router, "is_healthy", _always_healthy)
    yield router
    reset_registry_for_tests()
    reset_health_cache_for_tests()
    reset_routing_metrics_for_tests()
    reset_routing_repository_for_tests()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_policy_prefers_default_provider(fresh_router):
    decision = await fresh_router.route(model="llama3.2", policy="default")
    assert decision.provider_name == "ollama"
    assert decision.policy == "default"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_preferred_provider_policy(fresh_router, monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_DEFAULT_PROVIDER",
        "openai",
        raising=False,
    )
    # Shared ownership so preferred can win among healthy candidates
    monkeypatch.setattr(
        fresh_router,
        "_owners_of_model",
        lambda _m: ["ollama", "openai"],
    )
    decision = await fresh_router.route(model="shared-model", policy="preferred_provider")
    assert decision.provider_name == "openai"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cheapest_policy(fresh_router, monkeypatch):
    monkeypatch.setattr(
        fresh_router,
        "_owners_of_model",
        lambda _m: ["openai", "ollama", "gemini"],
    )
    decision = await fresh_router.route(model="shared-model", policy="cheapest")
    assert decision.provider_name == "ollama"  # cost 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fastest_policy(fresh_router, monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_VLLM", True, raising=False
    )
    reset_registry_for_tests()
    ensure_providers_registered()
    monkeypatch.setattr(
        fresh_router,
        "_owners_of_model",
        lambda _m: ["ollama", "openai", "vllm"],
    )
    decision = await fresh_router.route(model="shared-model", policy="fastest")
    assert decision.provider_name == "vllm"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_highest_quality_policy(fresh_router, monkeypatch):
    monkeypatch.setattr(
        fresh_router,
        "_owners_of_model",
        lambda _m: ["openai", "anthropic", "ollama"],
    )
    decision = await fresh_router.route(model="shared-model", policy="highest_quality")
    assert decision.provider_name == "anthropic"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_aware_skips_unhealthy(fresh_router, monkeypatch):
    monkeypatch.setattr(
        fresh_router,
        "_owners_of_model",
        lambda _m: ["ollama", "openai"],
    )

    async def _health(provider) -> bool:
        return provider.name != "ollama"

    monkeypatch.setattr(fresh_router, "is_healthy", _health)
    decision = await fresh_router.route(model="shared-model", policy="default")
    assert decision.provider_name == "openai"
    assert "ollama" in decision.skipped_unhealthy


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_unhealthy_returns_503(fresh_router, monkeypatch):
    monkeypatch.setattr(
        fresh_router,
        "_owners_of_model",
        lambda _m: ["ollama", "openai"],
    )

    async def _unhealthy(_provider) -> bool:
        return False

    monkeypatch.setattr(fresh_router, "is_healthy", _unhealthy)
    with pytest.raises(HTTPException) as exc:
        await fresh_router.route(model="shared-model")
    assert exc.value.status_code == 503
    assert exc.value.detail["error"]["code"] == "no_healthy_provider"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_model_404(fresh_router):
    with pytest.raises(HTTPException) as exc:
        await fresh_router.route(model="does-not-exist-xyz")
    assert exc.value.status_code == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_provider_400(fresh_router):
    with pytest.raises(HTTPException) as exc:
        await fresh_router.route(model="llama3.2", provider="nope")
    assert exc.value.status_code == 400


@pytest.mark.unit
@pytest.mark.asyncio
async def test_capability_filter_embeddings(fresh_router, monkeypatch):
    # Anthropic has chat only — embeddings capability should exclude it even if listed
    monkeypatch.setattr(
        fresh_router,
        "_owners_of_model",
        lambda _m: ["anthropic", "openai"],
    )
    decision = await fresh_router.route(
        model="embed-shared",
        capability=ProviderCapability.EMBEDDINGS,
        policy="cheapest",
    )
    assert decision.provider_name == "openai"
    assert decision.capability == "embeddings"


@pytest.mark.unit
def test_provider_capabilities_map(fresh_router):
    svc = InferenceRoutingService(router=fresh_router)
    caps = svc.capabilities_map()
    assert "chat" in caps["ollama"]
    assert "embeddings" in caps["ollama"]
    assert "image_generation" in caps["openai"]
    assert "speech_to_text" in caps["openai"]
    assert "text_to_speech" in caps["openai"]
    assert "chat" in caps["anthropic"]
    assert "embeddings" not in caps["anthropic"]


@pytest.mark.unit
def test_provider_priority_env_override(fresh_router, monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_PROVIDER_PRIORITY",
        "gemini,openai,ollama",
        raising=False,
    )
    order = fresh_router.repository.priority_order()
    assert order[:3] == ["gemini", "openai", "ollama"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_cache_ttl(monkeypatch):
    reset_health_cache_for_tests(ttl_seconds=60.0)
    cache = get_health_cache()
    calls = {"n": 0}

    async def probe():
        calls["n"] += 1
        return {"ok": True, "n": calls["n"]}

    first = await cache.get_or_probe("ollama", probe)
    second = await cache.get_or_probe("ollama", probe)
    assert first["ok"] is True
    assert first["cached"] is False
    assert second["cached"] is True
    assert calls["n"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_routing_metrics_recorded(fresh_router):
    reset_routing_metrics_for_tests()
    decision = await fresh_router.route(model="gpt-4o-mini", policy="default")
    snap = fresh_router.metrics.snapshot()
    assert snap["provider_selected"].get(decision.provider_name, 0) >= 1
    assert snap["routing_time_ms"]["count"] >= 1
    assert snap["policy_selected"].get("default", 0) >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_chat_records_latency(fresh_router, monkeypatch):
    reset_routing_metrics_for_tests()
    monkeypatch.setattr(
        "app.config.settings.settings.OPENAI_API_KEY", "sk-test", raising=False
    )
    svc = InferenceRoutingService(router=fresh_router)
    result, decision = await svc.chat(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        provider="openai",
    )
    assert result["object"] == "chat.completion"
    assert decision.provider_name == "openai"
    snap = svc.metrics_snapshot()
    assert snap["provider_latency_ms"]["openai"]["count"] >= 1
    assert snap["provider_errors"].get("openai", 0) == 0
