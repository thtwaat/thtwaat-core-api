"""Unit tests — tenant rate limiting for openai_compat (Week 2 Day 4)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.openai_compat.cache import set_redis_client_for_tests
from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.rate_limit import (
    OpenAICompatRateLimiter,
    limits_for_plan,
    resolve_plan_name,
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
def test_limits_for_plan_defaults():
    free = limits_for_plan("free", "completions")
    assert free["rpm"] == 20
    assert free["rpd"] == 200
    ent = limits_for_plan("enterprise", "completions")
    assert ent["rpm"] >= free["rpm"]
    models = limits_for_plan("free", "models")
    assert models["rpm"] >= free["rpm"]


@pytest.mark.unit
def test_resolve_plan_falls_back_to_free(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.settings.OPENAI_COMPAT_RATE_LIMIT_DEFAULT_PLAN",
        "free",
        raising=False,
    )
    db = MagicMock()
    db.query.side_effect = Exception("no db")
    assert resolve_plan_name(db, uuid.uuid4()) == "free"


@pytest.mark.unit
def test_rate_limiter_allows_under_limit(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.settings.OPENAI_COMPAT_RATE_LIMIT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "free",
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.limits_for_plan",
        lambda *_a, **_k: {"rpm": 5, "rpd": 100},
    )
    limiter = OpenAICompatRateLimiter(MagicMock(), client=fake_redis_client)
    company_id = uuid.uuid4()
    for _ in range(5):
        d = limiter.enforce(company_id, scope="completions")
        assert d.allowed is True
    assert d.remaining == 0


@pytest.mark.unit
def test_rate_limiter_429_with_retry_after(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.settings.OPENAI_COMPAT_RATE_LIMIT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "free",
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.limits_for_plan",
        lambda *_a, **_k: {"rpm": 2, "rpd": 100},
    )
    limiter = OpenAICompatRateLimiter(MagicMock(), client=fake_redis_client)
    company_id = uuid.uuid4()
    limiter.enforce(company_id, scope="completions")
    limiter.enforce(company_id, scope="completions")
    with pytest.raises(HTTPException) as exc:
        limiter.enforce(company_id, scope="completions")
    assert exc.value.status_code == 429
    assert exc.value.detail["error"]["code"] == "rate_limit_exceeded"
    assert "Retry-After" in (exc.value.headers or {})
    assert int(exc.value.headers["Retry-After"]) >= 1


@pytest.mark.unit
def test_route_sets_rate_limit_headers(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.settings.OPENAI_COMPAT_RATE_LIMIT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "starter",
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
        id="chatcmpl_rl",
        created=1,
        model="thtwaat-stub-mini",
        choices=[ChatCompletionChoice(message=ChatCompletionMessage(content="ok"))],
        usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )

    with patch.object(
        CompletionsService,
        "create_completion",
        new=AsyncMock(return_value=(fake_resp, "BYPASS")),
    ):
        client = TestClient(app)
        r = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer tht_key_x"},
            json={
                "model": "thtwaat-stub-mini",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )
    assert r.status_code == 200
    assert r.headers.get("x-ratelimit-limit")
    assert r.headers.get("x-ratelimit-remaining") is not None
    assert r.headers.get("x-ratelimit-reset")
    assert r.headers.get("x-ratelimit-plan") == "starter"


@pytest.mark.unit
def test_idempotent_replay_skips_rate_limit(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.settings.OPENAI_COMPAT_RATE_LIMIT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "free",
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.limits_for_plan",
        lambda *_a, **_k: {"rpm": 1, "rpd": 100},
    )
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
        id="chatcmpl_once",
        created=1,
        model="m",
        choices=[ChatCompletionChoice(message=ChatCompletionMessage(content="once"))],
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
            "Idempotency-Key": "only-once",
        }
        payload = {"model": "m", "messages": [{"role": "user", "content": "x"}]}
        r1 = client.post("/v1/chat/completions", headers=headers, json=payload)
        r2 = client.post("/v1/chat/completions", headers=headers, json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.headers.get("idempotent-replayed") == "true"
    assert mocked.await_count == 1
