"""Unit tests — Redis caching for openai_compat (Week 2 Day 2)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.openai_compat.cache import (
    OpenAICompatCache,
    fingerprint_completion_request,
    set_redis_client_for_tests,
)
from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.models_service import ModelsService
from app.openai_compat.router import router as openai_compat_router
from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage
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
def test_fingerprint_stable():
    a = fingerprint_completion_request({"model": "m", "messages": [{"role": "user", "content": "x"}]})
    b = fingerprint_completion_request({"messages": [{"role": "user", "content": "x"}], "model": "m"})
    assert a == b
    c = fingerprint_completion_request({"model": "m", "messages": [{"role": "user", "content": "y"}]})
    assert a != c


@pytest.mark.unit
def test_models_list_cache_hit_miss_invalidate(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        True,
        raising=False,
    )
    company_id = uuid.uuid4()
    db = MagicMock()
    monkeypatch.setattr(
        "app.openai_compat.catalog.company_db_models",
        lambda *_a, **_k: [],
    )
    cache = OpenAICompatCache(client=fake_redis_client)
    svc = ModelsService(db, cache=cache)

    first, status1 = svc.list_models(company_id)
    second, status2 = svc.list_models(company_id)
    assert status1 == "MISS"
    assert status2 == "HIT"
    assert first.object == "list"
    assert any(m.id == "thtwaat-stub-mini" for m in first.data)
    assert second.data == first.data

    cache.invalidate_models(company_id)
    third, status3 = svc.list_models(company_id)
    assert status3 == "MISS"
    assert len(third.data) == len(first.data)


@pytest.mark.unit
def test_model_by_id_cached(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.catalog.company_db_models",
        lambda *_a, **_k: [],
    )
    company_id = uuid.uuid4()
    cache = OpenAICompatCache(client=fake_redis_client)
    svc = ModelsService(MagicMock(), cache=cache)

    m1, s1 = svc.get_model(company_id, "thtwaat-stub-mini")
    m2, s2 = svc.get_model(company_id, "thtwaat-stub-mini")
    assert m1.id == "thtwaat-stub-mini"
    assert s1 == "MISS"
    assert s2 == "HIT"
    assert m2.owned_by == "thtwaat"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_completion_response_cache_temp_zero(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_RESPONSES",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False},
    )

    cache = OpenAICompatCache(client=fake_redis_client)
    svc = CompletionsService(MagicMock(), cache=cache)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda row: row

    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="thtwaat-stub-mini",
        messages=[ChatMessage(role="user", content="Deterministic")],
        temperature=0,
    )
    r1, s1 = await svc.create_completion(principal, body)
    r2, s2 = await svc.create_completion(principal, body)
    assert s1 == "MISS"
    assert s2 == "HIT"
    assert r1.id == r2.id
    assert r1.choices[0].message.content == r2.choices[0].message.content
    assert svc.repo.create.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_completion_skips_cache_when_temperature_nonzero(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False},
    )

    cache = OpenAICompatCache(client=fake_redis_client)
    svc = CompletionsService(MagicMock(), cache=cache)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda row: row

    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="thtwaat-stub-mini",
        messages=[ChatMessage(role="user", content="Creative")],
        temperature=0.7,
    )
    _, s1 = await svc.create_completion(principal, body)
    _, s2 = await svc.create_completion(principal, body)
    assert s1 == "BYPASS"
    assert s2 == "BYPASS"
    assert svc.repo.create.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_responses(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_RESPONSES",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False},
    )

    cache = OpenAICompatCache(client=fake_redis_client)
    svc = CompletionsService(MagicMock(), cache=cache)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda row: row
    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="thtwaat-stub-mini",
        messages=[ChatMessage(role="user", content="x")],
        temperature=0,
    )
    await svc.create_completion(principal, body)
    cache.invalidate_responses(principal.company_id)
    _, status = await svc.create_completion(principal, body)
    assert status == "MISS"


@pytest.mark.unit
def test_route_models_x_cache_header(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.catalog.company_db_models",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "free",
    )

    app = FastAPI()
    app.include_router(openai_compat_router)
    principal = CompletionsPrincipal(company_id=uuid.uuid4())

    from app.database.database import get_db
    from app.openai_compat.dependencies import resolve_completions_principal

    app.dependency_overrides[resolve_completions_principal] = lambda: principal
    app.dependency_overrides[get_db] = lambda: MagicMock()

    client = TestClient(app)
    r1 = client.get("/v1/models", headers={"Authorization": "Bearer tht_key_x"})
    r2 = client.get("/v1/models", headers={"Authorization": "Bearer tht_key_x"})
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") == "MISS"
    assert r2.headers.get("x-cache") == "HIT"
    assert r1.json()["object"] == "list"
