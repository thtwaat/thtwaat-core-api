"""Week 4 gate — milestone harden (Day 6)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.orm_bootstrap import register_orm_models
from app.openai_compat.rate_limit import OpenAICompatRateLimiter
from app.openai_compat.router import router as openai_compat_router
from app.webhooks.model import (
    WEBHOOK_DELIVERY_DELIVERED,
    WEBHOOK_DELIVERY_PENDING,
    WEBHOOK_DELIVERY_QUEUED,
)
from app.webhooks.url_safety import UnsafeWebhookUrlError, assert_safe_webhook_url


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.unit
def test_chat_completions_auth_gated_json_and_stream():
    app = FastAPI()
    app.include_router(openai_compat_router)
    from app.database.database import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)
    body = {"model": "m", "messages": [{"role": "user", "content": "x"}]}
    assert client.post("/v1/chat/completions", json={**body, "stream": False}).status_code == 401
    assert client.post("/v1/chat/completions", json={**body, "stream": True}).status_code == 401


@pytest.mark.unit
def test_outbox_status_constants_stable():
    assert WEBHOOK_DELIVERY_PENDING == "pending"
    assert WEBHOOK_DELIVERY_QUEUED == "queued"
    assert WEBHOOK_DELIVERY_DELIVERED == "delivered"
    from app.webhooks import outbox

    assert hasattr(outbox, "record_pending_delivery")
    assert hasattr(outbox, "redrive_stuck_deliveries")
    assert hasattr(outbox, "ack_from_job_payload")


@pytest.mark.unit
def test_ssrf_guard_blocks_loopback(monkeypatch):
    monkeypatch.setattr(
        "app.webhooks.url_safety.settings.WEBHOOK_URL_SSRF_GUARD_ENABLED",
        True,
        raising=False,
    )
    with pytest.raises(UnsafeWebhookUrlError):
        assert_safe_webhook_url("https://127.0.0.1/hooks")


@pytest.mark.unit
def test_orm_bootstrap_registers():
    register_orm_models()
    register_orm_models()


@pytest.mark.unit
def test_rate_limit_fail_open_on_redis_error(monkeypatch):
    class Broken:
        def incr(self, *_a, **_k):
            raise ConnectionError("down")

        def expire(self, *_a, **_k):
            raise ConnectionError("down")

        def ttl(self, *_a, **_k):
            raise ConnectionError("down")

        def get(self, *_a, **_k):
            raise ConnectionError("down")

    monkeypatch.setattr(
        "app.openai_compat.rate_limit.settings.OPENAI_COMPAT_RATE_LIMIT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "free",
    )
    decision = OpenAICompatRateLimiter(db=MagicMock(), client=Broken()).check(
        __import__("uuid").uuid4(), scope="completions"
    )
    assert decision.allowed is True


@pytest.mark.unit
def test_week4_docs_exist():
    week4 = ROOT / "docs" / "course" / "ai-platform-engineering" / "semester-02" / "week-04"
    for name in (
        "THREAT_MODEL.md",
        "SHIP_CHECKLIST.md",
        "day-01.md",
        "day-02.md",
        "day-03.md",
        "day-04.md",
        "day-05.md",
        "day-06.md",
    ):
        assert (week4 / name).is_file(), name
    assert (ROOT / "docs" / "partners" / "openai-compat-sse.md").is_file()
    assert (ROOT / "performance" / "k6" / "openai_compat.js").is_file()
    assert (ROOT / "scripts" / "smoke_w4_openai_compat.sh").is_file()


@pytest.mark.unit
def test_models_and_usage_routes_registered():
    app = FastAPI()
    app.include_router(openai_compat_router)
    paths = app.openapi()["paths"]
    assert "/v1/models" in paths
    assert "/v1/chat/completions" in paths
    assert "/v1/usage" in paths
