"""Semester 03 Week 1 Day 4 — timeouts, missing models, 502/504 mapping."""
from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

from app.openai_compat.errors import (
    map_provider_exception,
    model_not_found,
    no_healthy_provider,
    unknown_provider,
    wrap_httpx_error,
)
from app.openai_compat.providers.base import (
    ProviderConfigError,
    ProviderTimeoutError,
    ProviderUpstreamError,
)
from app.openai_compat.providers.ollama import OllamaInferenceProvider


@pytest.mark.unit
def test_model_not_found_shape():
    exc = model_not_found("missing-model")
    assert exc.status_code == 404
    assert exc.detail["error"]["code"] == "model_not_found"


@pytest.mark.unit
def test_unknown_provider_shape():
    exc = unknown_provider("nope")
    assert exc.status_code == 400
    assert exc.detail["error"]["code"] == "unknown_provider"


@pytest.mark.unit
def test_no_healthy_provider_shape():
    exc = no_healthy_provider("llama3.2", ["ollama"])
    assert exc.status_code == 503
    assert exc.detail["error"]["code"] == "no_healthy_provider"


@pytest.mark.unit
def test_map_timeout_to_504():
    mapped = map_provider_exception(ProviderTimeoutError("slow", provider="ollama"))
    assert mapped.status_code == 504
    assert mapped.detail["error"]["code"] == "upstream_timeout"


@pytest.mark.unit
def test_map_httpx_timeout_to_504():
    mapped = map_provider_exception(httpx.ReadTimeout("read timed out"))
    assert mapped.status_code == 504
    assert mapped.detail["error"]["code"] == "upstream_timeout"


@pytest.mark.unit
def test_map_upstream_to_502():
    mapped = map_provider_exception(
        ProviderUpstreamError("bad gateway", provider="ollama", status_code=500)
    )
    assert mapped.status_code == 502
    assert mapped.detail["error"]["code"] == "upstream_error"


@pytest.mark.unit
def test_map_config_error():
    mapped = map_provider_exception(ProviderConfigError("OLLAMA_URL missing"))
    assert mapped.status_code == 502
    assert mapped.detail["error"]["code"] == "provider_config_error"


@pytest.mark.unit
def test_map_preserves_http_exception():
    original = model_not_found("x")
    assert map_provider_exception(original) is original


@pytest.mark.unit
def test_wrap_httpx_timeout():
    err = wrap_httpx_error(httpx.ConnectTimeout("connect"), provider="ollama")
    assert isinstance(err, ProviderTimeoutError)
    assert err.provider == "ollama"


@pytest.mark.unit
def test_wrap_httpx_status():
    request = httpx.Request("POST", "http://ollama/api/chat")
    response = httpx.Response(502, request=request)
    status_err = httpx.HTTPStatusError("boom", request=request, response=response)
    err = wrap_httpx_error(status_err, provider="ollama")
    assert isinstance(err, ProviderUpstreamError)
    assert err.status_code == 502


@pytest.mark.unit
def test_ollama_timeout_setting(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.settings.INFERENCE_OLLAMA_TIMEOUT_SECONDS",
        7.5,
        raising=False,
    )
    prov = OllamaInferenceProvider()
    assert prov._timeout_seconds() == 7.5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_maps_timeout_via_gateway(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    import uuid

    from app.openai_compat.dependencies import CompletionsPrincipal
    from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage
    from app.openai_compat.service import CompletionsService

    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "gateway",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False},
    )
    monkeypatch.setattr(
        "app.openai_compat.inference_routing_service.InferenceRoutingService.chat",
        AsyncMock(side_effect=ProviderTimeoutError("timed out", provider="ollama")),
    )
    db = MagicMock()
    svc = CompletionsService(db)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda row: row

    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="llama3.2",
        messages=[ChatMessage(role="user", content="Hi")],
    )
    with pytest.raises(HTTPException) as exc:
        await svc.create_completion(principal, body)

    assert exc.value.status_code == 504
    assert exc.value.detail["error"]["code"] == "upstream_timeout"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_router_http_exception_not_rewritten(monkeypatch):
    """Router 404 must propagate — not become upstream_error."""
    from unittest.mock import AsyncMock, MagicMock
    import uuid

    from app.openai_compat.dependencies import CompletionsPrincipal
    from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage
    from app.openai_compat.service import CompletionsService

    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "gateway",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False},
    )
    db = MagicMock()
    svc = CompletionsService(db)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda row: row

    with pytest.raises(HTTPException) as exc:
        monkeypatch.setattr(
            "app.openai_compat.inference_routing_service.InferenceRoutingService.chat",
            AsyncMock(side_effect=model_not_found("totally-missing")),
        )
        principal = CompletionsPrincipal(company_id=uuid.uuid4())
        body = ChatCompletionRequest(
            model="totally-missing",
            messages=[ChatMessage(role="user", content="Hi")],
        )
        await svc.create_completion(principal, body)

    assert exc.value.status_code == 404
    assert exc.value.detail["error"]["code"] == "model_not_found"
