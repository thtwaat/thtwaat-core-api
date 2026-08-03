"""Semester 03 Week 1 Day 2 — provider registry & default routing."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.openai_compat.providers import ensure_providers_registered
from app.openai_compat.providers.registry import get_registry, reset_registry_for_tests
from app.openai_compat.providers.routing import (
    default_provider_name,
    resolve_provider_for_request,
    resolve_provider_name,
)


@pytest.fixture
def fresh_registry(monkeypatch):
    reset_registry_for_tests()
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
    ensure_providers_registered()
    yield get_registry()
    reset_registry_for_tests()


@pytest.mark.unit
def test_registry_registers_core_providers(fresh_registry):
    names = set(fresh_registry.registered_names())
    assert {"ollama", "openai", "gemini", "anthropic", "vllm"} <= names


@pytest.mark.unit
def test_default_provider_is_ollama(fresh_registry):
    assert default_provider_name() == "ollama"
    assert resolve_provider_name(None) == "ollama"
    assert resolve_provider_name("") == "ollama"
    name, prov = resolve_provider_for_request(provider=None, model="llama3.2")
    assert name == "ollama"
    assert prov.name == "ollama"


@pytest.mark.unit
def test_model_to_provider_resolution(fresh_registry):
    name, _ = resolve_provider_for_request(provider=None, model="gpt-4o-mini")
    assert name == "openai"
    name, _ = resolve_provider_for_request(provider=None, model="claude-3-5-sonnet")
    assert name == "anthropic"


@pytest.mark.unit
def test_unknown_provider_raises_400(fresh_registry):
    with pytest.raises(HTTPException) as exc:
        resolve_provider_for_request(provider="not-a-provider", model="llama3.2")
    assert exc.value.status_code == 400
    assert exc.value.detail["error"]["code"] == "unknown_provider"


@pytest.mark.unit
def test_unknown_model_raises_404(fresh_registry):
    with pytest.raises(HTTPException) as exc:
        resolve_provider_for_request(provider=None, model="totally-unknown-model")
    assert exc.value.status_code == 404
    assert exc.value.detail["error"]["code"] == "model_not_found"


@pytest.mark.unit
def test_disabled_provider_hidden_from_models(fresh_registry, monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_OPENAI", False, raising=False
    )
    # Re-instantiate so is_enabled reads new settings
    reset_registry_for_tests()
    ensure_providers_registered()
    registry = get_registry()
    assert "openai" not in registry.enabled_names()
    ids = {m["id"] for m in registry.all_enabled_models()}
    assert "gpt-4o-mini" not in ids
    assert "llama3.2" in ids
    with pytest.raises(HTTPException) as exc:
        resolve_provider_for_request(provider="openai", model="gpt-4o-mini")
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_multi_provider_model_listing(fresh_registry, monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_VLLM", True, raising=False
    )
    reset_registry_for_tests()
    ensure_providers_registered()
    registry = get_registry()
    ids = {m["id"] for m in registry.all_enabled_models()}
    assert "llama3.2" in ids
    assert "gpt-4o" in ids
    assert "gemini-1.5-flash" in ids
    assert "claude-3-5-sonnet" in ids
    assert "vllm-stub-mini" in ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_aggregate_health_continues_when_one_down(fresh_registry, monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.OPENAI_API_KEY", None, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.GEMINI_API_KEY", "g", raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.ANTHROPIC_API_KEY", "a", raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.settings.OLLAMA_URL",
        "http://ollama:11434",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.providers.ollama.probe_ollama",
        lambda *_a, **_k: {"ok": True, "latency_ms": 1},
    )
    reset_registry_for_tests()
    ensure_providers_registered()
    health = await get_registry().aggregate_health()
    assert "openai" in health["providers"]
    assert health["providers"]["openai"]["ok"] is False
    assert health["ok"] is True
    assert health["healthy_count"] >= 1


@pytest.mark.unit
def test_catalog_excludes_disabled(monkeypatch):
    from app.openai_compat.catalog import build_models_payload
    from unittest.mock import MagicMock

    monkeypatch.setattr(
        "app.config.settings.settings.OPENAI_COMPAT_INFERENCE",
        "gateway",
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_ENABLE_ANTHROPIC",
        False,
        raising=False,
    )
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
        "app.config.settings.settings.INFERENCE_ENABLE_VLLM", False, raising=False
    )
    reset_registry_for_tests()
    ensure_providers_registered()
    payload = build_models_payload(MagicMock(), __import__("uuid").uuid4())
    ids = {m["id"] for m in payload["data"]}
    assert "claude-3-5-sonnet" not in ids
    assert "llama3.2" in ids
