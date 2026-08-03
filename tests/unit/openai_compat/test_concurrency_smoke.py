"""Week 4 Day 3 — concurrency smoke for OpenAI-compatible completions."""
from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.openai_compat.cache import set_redis_client_for_tests
from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.idempotency import IdempotencyStore, hash_completion_body
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
@pytest.mark.asyncio
async def test_concurrent_stub_completions_unique_ids(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_WEBHOOKS_ENABLED",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False, "estimated_cost": 0.0},
    )

    db = MagicMock()
    svc = CompletionsService(db)
    svc.repo = MagicMock()
    svc.repo.create.side_effect = lambda row: row
    principal = CompletionsPrincipal(company_id=uuid.uuid4())

    async def _one(i: int):
        body = ChatCompletionRequest(
            model="thtwaat-stub-mini",
            messages=[ChatMessage(role="user", content=f"hi-{i}")],
            temperature=0.7,
            stream=False,
        )
        return await svc.create_completion(principal, body)

    results = await asyncio.gather(*[_one(i) for i in range(8)])
    ids = [r[0].id if isinstance(r, tuple) else r.id for r in results]
    assert len(ids) == 8
    assert len(set(ids)) == 8
    assert svc.repo.create.call_count == 8


@pytest.mark.unit
def test_concurrent_idempotency_only_one_proceeds(fake_redis_client, monkeypatch):
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
            "messages": [{"role": "user", "content": "race"}],
            "stream": False,
        }
    )

    outcomes: list[str] = []
    errors: list[str] = []

    def _race(_n: int) -> None:
        try:
            action, _ = store.begin_or_lookup(
                company_id=company_id,
                idempotency_key="w4-race-key",
                request_hash=body_hash,
            )
            outcomes.append(action)
        except HTTPException as exc:
            code = (exc.detail or {}).get("error", {}).get("code") if isinstance(exc.detail, dict) else None
            errors.append(str(code or exc.status_code))

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(_race, range(12)))

    assert outcomes.count("proceed") == 1
    assert len(outcomes) + len(errors) == 12
    assert all(e == "idempotency_in_progress" for e in errors)


@pytest.mark.unit
def test_orm_bootstrap_idempotent():
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()
    register_orm_models()  # second call no-op
