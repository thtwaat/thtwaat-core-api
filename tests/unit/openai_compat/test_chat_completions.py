"""Unit tests — OpenAI-compatible chat completions (Week 2 Day 1)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.router import router as openai_compat_router
from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage
from app.openai_compat.service import CompletionsService
from app.openai_compat.stub import estimate_tokens, stub_complete


@pytest.mark.unit
def test_estimate_tokens_heuristic():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10


@pytest.mark.unit
def test_stub_complete_includes_model_and_usage():
    messages = [ChatMessage(role="user", content="Hello world")]
    content, prompt_tokens, completion_tokens = stub_complete(messages, model="thtwaat-stub-mini")
    assert "thtwaat-stub-mini" in content
    assert prompt_tokens >= 1
    assert completion_tokens >= 1
    assert "[thtwaat-stub:" in content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_rejects_stream(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    db = MagicMock()
    svc = CompletionsService(db)
    svc.repo = MagicMock()
    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="m",
        messages=[ChatMessage(role="user", content="hi")],
        stream=True,
    )
    with pytest.raises(HTTPException) as exc:
        await svc.create_completion(principal, body)
    assert exc.value.status_code == 400
    assert exc.value.detail["error"]["code"] == "stream_not_supported"
    svc.repo.create.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_stub_persists_and_shapes_openai_response(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    db = MagicMock()
    svc = CompletionsService(db)
    captured = {}

    def _create(row):
        captured["row"] = row
        return row

    svc.repo = MagicMock()
    svc.repo.create.side_effect = _create

    principal = CompletionsPrincipal(
        company_id=uuid.uuid4(),
        api_key_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        auth_kind="agent_key",
    )
    body = ChatCompletionRequest(
        model="thtwaat-stub-mini",
        messages=[ChatMessage(role="user", content="Ping")],
    )
    resp, cache_status = await svc.create_completion(principal, body)

    assert cache_status == "BYPASS"
    assert resp.object == "chat.completion"
    assert resp.id.startswith("chatcmpl_")
    assert resp.model == "thtwaat-stub-mini"
    assert resp.choices[0].message.role == "assistant"
    assert "thtwaat-stub" in resp.choices[0].message.content
    assert resp.usage.total_tokens == resp.usage.prompt_tokens + resp.usage.completion_tokens
    assert captured["row"].company_id == principal.company_id
    assert captured["row"].completion_id == resp.id
    assert captured["row"].provider == "stub"
    assert captured["row"].status == "succeeded"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_gateway_mode_delegates(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "gateway",
        raising=False,
    )
    db = MagicMock()
    svc = CompletionsService(db)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda row: row

    fake = MagicMock(
        content="live answer",
        input_tokens=3,
        output_tokens=5,
        provider="openai",
        finish_reason="stop",
    )
    with patch(
        "app.agent_platform.gateway.service.AIGatewayService.process_request",
        new=AsyncMock(return_value=fake),
    ) as mocked:
        principal = CompletionsPrincipal(company_id=uuid.uuid4())
        body = ChatCompletionRequest(
            model="gpt-4o-mini",
            messages=[ChatMessage(role="user", content="Hi")],
            provider="openai",
        )
        resp, _cache_status = await svc.create_completion(principal, body)

    mocked.assert_awaited_once()
    assert resp.choices[0].message.content == "live answer"
    assert resp.usage.prompt_tokens == 3
    assert resp.usage.completion_tokens == 5
    assert resp.system_fingerprint == "thtwaat-openai"


def _client_with_principal(principal: CompletionsPrincipal) -> TestClient:
    app = FastAPI()
    app.include_router(openai_compat_router)

    async def _principal_override():
        return principal

    from app.openai_compat.dependencies import resolve_completions_principal
    from app.database.database import get_db

    app.dependency_overrides[resolve_completions_principal] = _principal_override
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app)


@pytest.mark.unit
def test_route_401_without_auth():
    app = FastAPI()
    app.include_router(openai_compat_router)
    from app.database.database import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)
    r = client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "x"}]},
    )
    assert r.status_code == 401


@pytest.mark.unit
def test_route_stub_success(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    principal = CompletionsPrincipal(company_id=uuid.uuid4(), auth_kind="company_key")
    client = _client_with_principal(principal)

    with patch.object(CompletionsService, "create_completion", new_callable=AsyncMock) as mocked:
        from app.openai_compat.schemas import (
            ChatCompletionChoice,
            ChatCompletionMessage,
            ChatCompletionResponse,
            CompletionUsage,
        )

        mocked.return_value = (
            ChatCompletionResponse(
                id="chatcmpl_test",
                created=1,
                model="thtwaat-stub-mini",
                choices=[
                    ChatCompletionChoice(
                        message=ChatCompletionMessage(content="ok"),
                    )
                ],
                usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            ),
            "BYPASS",
        )
        r = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer tht_key_dummy"},
            json={
                "model": "thtwaat-stub-mini",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "chatcmpl_test"
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "ok"


@pytest.mark.unit
def test_openapi_includes_completions_path():
    app = FastAPI()
    app.include_router(openai_compat_router)
    schema = app.openapi()
    path = schema["paths"]["/v1/chat/completions"]["post"]
    assert path.get("summary")
    assert "requestBody" in path
