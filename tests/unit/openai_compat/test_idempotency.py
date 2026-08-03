"""Unit tests — Idempotency-Key for openai_compat (Week 2 Day 3)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.openai_compat.cache import set_redis_client_for_tests
from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.idempotency import (
    IdempotencyStore,
    hash_completion_body,
    validate_idempotency_key,
)
from app.openai_compat.router import router as openai_compat_router
from app.openai_compat.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionResponse,
    CompletionUsage,
)
from app.openai_compat.service import CompletionsService


@pytest.fixture
def fake_redis_client():
    fakeredis = pytest.importorskip("fakeredis")
    client = fakeredis.FakeRedis(decode_responses=True)
    set_redis_client_for_tests(client)
    yield client
    client.flushall()
    set_redis_client_for_tests(None)


@pytest.mark.unit
def test_validate_idempotency_key_accepts_common_forms():
    assert validate_idempotency_key("order-42") == "order-42"
    assert validate_idempotency_key("  a/b:c_d=1+2  ") == "a/b:c_d=1+2"


@pytest.mark.unit
def test_validate_idempotency_key_rejects_bad():
    with pytest.raises(HTTPException) as exc:
        validate_idempotency_key("bad key with spaces!")
    assert exc.value.status_code == 400
    assert exc.value.detail["error"]["code"] == "invalid_idempotency_key"


@pytest.mark.unit
def test_store_replay_same_body(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.idempotency.settings.OPENAI_COMPAT_IDEMPOTENCY_ENABLED",
        True,
        raising=False,
    )
    store = IdempotencyStore(client=fake_redis_client)
    company_id = uuid.uuid4()
    body_hash = hash_completion_body({"model": "m", "messages": [{"role": "user", "content": "hi"}]})

    action, _ = store.begin_or_lookup(
        company_id=company_id, idempotency_key="k1", request_hash=body_hash
    )
    assert action == "proceed"
    store.complete(
        company_id=company_id,
        idempotency_key="k1",
        request_hash=body_hash,
        response={"id": "chatcmpl_1", "object": "chat.completion", "created": 1, "model": "m",
                  "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                               "finish_reason": "stop", "logprobs": None}],
                  "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
    )
    action2, record = store.begin_or_lookup(
        company_id=company_id, idempotency_key="k1", request_hash=body_hash
    )
    assert action2 == "replay"
    assert record is not None
    assert record.response["id"] == "chatcmpl_1"


@pytest.mark.unit
def test_store_conflict_on_body_mismatch(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.idempotency.settings.OPENAI_COMPAT_IDEMPOTENCY_ENABLED",
        True,
        raising=False,
    )
    store = IdempotencyStore(client=fake_redis_client)
    company_id = uuid.uuid4()
    h1 = hash_completion_body({"model": "m", "messages": [{"role": "user", "content": "a"}]})
    h2 = hash_completion_body({"model": "m", "messages": [{"role": "user", "content": "b"}]})
    store.begin_or_lookup(company_id=company_id, idempotency_key="k1", request_hash=h1)
    store.complete(
        company_id=company_id,
        idempotency_key="k1",
        request_hash=h1,
        response={"id": "x", "object": "chat.completion", "created": 1, "model": "m",
                  "choices": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}},
    )
    with pytest.raises(HTTPException) as exc:
        store.begin_or_lookup(company_id=company_id, idempotency_key="k1", request_hash=h2)
    assert exc.value.status_code == 409
    assert exc.value.detail["error"]["code"] == "idempotency_key_reuse"


@pytest.mark.unit
def test_store_in_progress_conflict(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.idempotency.settings.OPENAI_COMPAT_IDEMPOTENCY_ENABLED",
        True,
        raising=False,
    )
    store = IdempotencyStore(client=fake_redis_client)
    company_id = uuid.uuid4()
    h = hash_completion_body({"model": "m", "messages": []})
    store.begin_or_lookup(company_id=company_id, idempotency_key="k1", request_hash=h)
    with pytest.raises(HTTPException) as exc:
        store.begin_or_lookup(company_id=company_id, idempotency_key="k1", request_hash=h)
    assert exc.value.status_code == 409
    assert exc.value.detail["error"]["code"] == "idempotency_in_progress"


@pytest.mark.unit
def test_route_idempotent_replay(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.idempotency.settings.OPENAI_COMPAT_IDEMPOTENCY_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )

    app = FastAPI()
    app.include_router(openai_compat_router)
    principal = CompletionsPrincipal(company_id=uuid.uuid4())

    from app.database.database import get_db
    from app.openai_compat.dependencies import resolve_completions_principal

    app.dependency_overrides[resolve_completions_principal] = lambda: principal
    app.dependency_overrides[get_db] = lambda: MagicMock()

    fake_resp = ChatCompletionResponse(
        id="chatcmpl_live",
        created=1,
        model="thtwaat-stub-mini",
        choices=[ChatCompletionChoice(message=ChatCompletionMessage(content="hello"))],
        usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )

    with patch.object(
        CompletionsService,
        "create_completion",
        new=AsyncMock(return_value=(fake_resp, "BYPASS")),
    ) as mocked:
        client = TestClient(app)
        headers = {
            "Authorization": "Bearer tht_key_x",
            "Idempotency-Key": "checkout-99",
        }
        payload = {
            "model": "thtwaat-stub-mini",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.7,
        }
        r1 = client.post("/v1/chat/completions", headers=headers, json=payload)
        r2 = client.post("/v1/chat/completions", headers=headers, json=payload)

    assert r1.status_code == 200
    assert r1.headers.get("idempotent-replayed") == "false"
    assert r2.status_code == 200
    assert r2.headers.get("idempotent-replayed") == "true"
    assert r1.json()["id"] == r2.json()["id"] == "chatcmpl_live"
    assert mocked.await_count == 1


@pytest.mark.unit
def test_route_idempotent_body_mismatch_409(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.idempotency.settings.OPENAI_COMPAT_IDEMPOTENCY_ENABLED",
        True,
        raising=False,
    )

    app = FastAPI()
    app.include_router(openai_compat_router)
    principal = CompletionsPrincipal(company_id=uuid.uuid4())

    from app.database.database import get_db
    from app.openai_compat.dependencies import resolve_completions_principal

    app.dependency_overrides[resolve_completions_principal] = lambda: principal
    app.dependency_overrides[get_db] = lambda: MagicMock()

    fake_resp = ChatCompletionResponse(
        id="chatcmpl_a",
        created=1,
        model="m",
        choices=[ChatCompletionChoice(message=ChatCompletionMessage(content="a"))],
        usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )

    with patch.object(
        CompletionsService,
        "create_completion",
        new=AsyncMock(return_value=(fake_resp, "BYPASS")),
    ):
        client = TestClient(app)
        headers = {"Authorization": "Bearer tht_key_x", "Idempotency-Key": "same-key"}
        client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "m", "messages": [{"role": "user", "content": "one"}]},
        )
        r2 = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "m", "messages": [{"role": "user", "content": "two"}]},
        )
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"]["code"] == "idempotency_key_reuse"
