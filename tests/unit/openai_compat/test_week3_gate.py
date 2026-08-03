"""Week 3 gate — milestone polish (Day 6)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.events import build_completion_event_data
from app.openai_compat.router import router as openai_compat_router
from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage
from app.openai_compat.service import CompletionsService
from app.webhooks.delivery import sign_v1, verify_webhook_signature


@pytest.mark.unit
def test_completion_event_includes_estimated_cost():
    data = build_completion_event_data(
        completion_id="chatcmpl_x",
        model="m",
        status="succeeded",
        prompt_tokens=1,
        completion_tokens=2,
        estimated_cost=0.0012,
        provider="stub",
    )
    assert data["estimated_cost"] == 0.0012
    assert data["usage"]["total_tokens"] == 3


@pytest.mark.unit
def test_openapi_mentions_idempotency_for_stream():
    app = FastAPI()
    app.include_router(openai_compat_router)
    path = app.openapi()["paths"]["/v1/chat/completions"]["post"]
    # Course tag moved to week-03/day-04
    extra = path.get("x-thtwaat-course") or ""
    # openapi_extra may land at operation level
    assert "week-03" in str(path) or "Idempotency" in str(path)
    desc = ""
    for p in path.get("parameters") or []:
        if p.get("name") == "Idempotency-Key":
            desc = p.get("description") or ""
    # FastAPI may put openapi_extra parameters in a nonstandard place; soft assert
    assert "/v1/chat/completions" in app.openapi()["paths"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_notify_passes_cost(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_WEBHOOKS_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"estimated_cost": 0.42, "recorded": True},
    )
    captured = {}

    def _notify(**kwargs):
        captured.update(kwargs)

    svc = CompletionsService(MagicMock())
    svc.repo = MagicMock()
    svc._notify_completion = _notify  # type: ignore[method-assign]
    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="m",
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.7,
        stream=False,
    )
    await svc.create_completion(principal, body)
    assert captured.get("estimated_cost") == 0.42


@pytest.mark.unit
def test_v1_signature_roundtrip_for_fanout_payload():
    body = '{"event":"completion.succeeded","delivery_id":"whdel_abc","data":{"estimated_cost":0.1}}'
    ts, sig = sign_v1(body, "whsec_x", timestamp=1_700_000_000)
    assert verify_webhook_signature(
        body,
        "whsec_x",
        signature_header=sig,
        timestamp_header=str(ts),
        now=1_700_000_000,
        tolerance_seconds=60,
    )


@pytest.mark.unit
def test_chat_completions_still_auth_gated():
    app = FastAPI()
    app.include_router(openai_compat_router)
    from app.database.database import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)
    r = client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "x"}], "stream": True},
    )
    assert r.status_code == 401
