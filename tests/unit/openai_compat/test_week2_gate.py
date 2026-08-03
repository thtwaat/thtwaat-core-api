"""Week 2 gate tests — contract harden (Days 6–7)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.openai_compat.cache import set_redis_client_for_tests
from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.models_service import ModelsService
from app.openai_compat.router import router as openai_compat_router


@pytest.fixture
def fake_redis_client():
    fakeredis = pytest.importorskip("fakeredis")
    client = fakeredis.FakeRedis(decode_responses=True)
    set_redis_client_for_tests(client)
    yield client
    client.flushall()
    set_redis_client_for_tests(None)


@pytest.mark.unit
def test_models_pagination_caps(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.catalog.company_db_models",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        False,
        raising=False,
    )
    svc = ModelsService(MagicMock())
    page, _ = svc.list_models(uuid.uuid4(), limit=2, offset=0)
    assert len(page.data) <= 2
    # oversize limit clamped
    page2, _ = svc.list_models(uuid.uuid4(), limit=500, offset=0)
    assert len(page2.data) <= 100


@pytest.mark.unit
def test_all_v1_routes_require_auth():
    app = FastAPI()
    app.include_router(openai_compat_router)
    from app.database.database import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)
    assert client.get("/v1/models").status_code == 401
    assert client.get("/v1/models/thtwaat-stub-mini").status_code == 401
    assert client.get("/v1/usage").status_code == 401
    assert client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "x"}]},
    ).status_code == 401


@pytest.mark.unit
def test_openapi_lists_week2_paths():
    app = FastAPI()
    app.include_router(openai_compat_router)
    paths = app.openapi()["paths"]
    assert "/v1/chat/completions" in paths
    assert "/v1/models" in paths
    assert "/v1/usage" in paths
    params = {p["name"] for p in paths["/v1/models"]["get"].get("parameters", [])}
    assert "limit" in params
    assert "offset" in params


@pytest.mark.unit
def test_models_route_pagination_query(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "free",
    )
    monkeypatch.setattr(
        "app.openai_compat.catalog.company_db_models",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
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
    client = TestClient(app)
    r = client.get(
        "/v1/models?limit=1&offset=0",
        headers={"Authorization": "Bearer tht_key_x"},
    )
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1
