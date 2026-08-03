"""Week 3 Day 4 — streaming × idempotency."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.openai_compat.cache import set_redis_client_for_tests
from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.idempotency import IdempotencyStore, hash_completion_body
from app.openai_compat.streaming import material_from_stored_response


@pytest.fixture
def fake_redis_client():
    fakeredis = pytest.importorskip("fakeredis")
    client = fakeredis.FakeRedis(decode_responses=True)
    set_redis_client_for_tests(client)
    yield client
    client.flushall()
    set_redis_client_for_tests(None)


@pytest.mark.unit
def test_hash_includes_stream_flag():
    base = {
        "company_id": "c",
        "model": "m",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.7,
        "max_tokens": None,
        "top_p": None,
        "stop": None,
        "provider": None,
        "n": 1,
        "user": None,
    }
    h_json = hash_completion_body({**base, "stream": False})
    h_sse = hash_completion_body({**base, "stream": True})
    assert h_json != h_sse


@pytest.mark.unit
def test_material_from_stored_response_roundtrip():
    stored = {
        "id": "chatcmpl_abc",
        "object": "chat.completion",
        "created": 1,
        "model": "thtwaat-stub-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from store"},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        "system_fingerprint": "thtwaat-stub",
    }
    material = material_from_stored_response(stored)
    assert material.completion_id == "chatcmpl_abc"
    assert material.content == "Hello from store"
    assert "".join(material.pieces) == "Hello from store"
    assert material.provider == "stub"
    assert material.prompt_tokens == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_idempotency_complete_then_replay(fake_redis_client, monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.idempotency.settings.OPENAI_COMPAT_IDEMPOTENCY_ENABLED",
        True,
        raising=False,
    )
    store = IdempotencyStore(client=fake_redis_client)
    company_id = uuid.uuid4()
    body_hash = hash_completion_body(
        {
            "company_id": str(company_id),
            "model": "m",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
    )
    action, _ = store.begin_or_lookup(
        company_id=company_id, idempotency_key="stream-k1", request_hash=body_hash
    )
    assert action == "proceed"
    stored = {
        "id": "chatcmpl_1",
        "model": "m",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        "system_fingerprint": "thtwaat-stub",
    }
    store.complete(
        company_id=company_id,
        idempotency_key="stream-k1",
        request_hash=body_hash,
        response=stored,
    )
    action2, record = store.begin_or_lookup(
        company_id=company_id, idempotency_key="stream-k1", request_hash=body_hash
    )
    assert action2 == "replay"
    assert record is not None
    material = material_from_stored_response(record.response or {})
    frames = []
    from app.openai_compat.streaming import aiter_sse_from_material

    async for frame in aiter_sse_from_material(material):
        frames.append(frame)
    assert frames[-1] == "data: [DONE]\n\n"
    assert any("ok" in f for f in frames)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_stream_material_persists(monkeypatch):
    from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage
    from app.openai_compat.service import CompletionsService

    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False},
    )
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_WEBHOOKS_ENABLED",
        False,
        raising=False,
    )
    svc = CompletionsService(MagicMock())
    svc.repo = MagicMock()
    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="m",
        messages=[ChatMessage(role="user", content="hi")],
        stream=True,
    )
    material = await svc.build_stream_material(principal, body)
    assert material.response["id"].startswith("chatcmpl_")
    assert material.content
    assert svc.repo.create.called
