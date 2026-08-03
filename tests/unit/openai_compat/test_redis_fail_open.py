"""Week 4 Day 4 — Redis fail-open behavior for openai_compat controls."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.openai_compat.cache import OpenAICompatCache
from app.openai_compat.idempotency import IdempotencyStore, hash_completion_body
from app.openai_compat.rate_limit import OpenAICompatRateLimiter


class _BrokenRedis:
    def get(self, *_a, **_k):
        raise ConnectionError("redis down")

    def set(self, *_a, **_k):
        raise ConnectionError("redis down")

    def setex(self, *_a, **_k):
        raise ConnectionError("redis down")

    def incr(self, *_a, **_k):
        raise ConnectionError("redis down")

    def expire(self, *_a, **_k):
        raise ConnectionError("redis down")

    def ttl(self, *_a, **_k):
        raise ConnectionError("redis down")

    def delete(self, *_a, **_k):
        raise ConnectionError("redis down")

    def scan_iter(self, **_k):
        raise ConnectionError("redis down")
        yield  # pragma: no cover


@pytest.mark.unit
def test_cache_get_fail_open_returns_none(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.cache.settings.OPENAI_COMPAT_CACHE_ENABLED",
        True,
        raising=False,
    )
    cache = OpenAICompatCache(client=_BrokenRedis())
    assert cache.get_json("any-key") is None
    assert cache.set_json("any-key", {"a": 1}, ttl=60) is False


@pytest.mark.unit
def test_rate_limit_fail_open_allows(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.settings.OPENAI_COMPAT_RATE_LIMIT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.rate_limit.resolve_plan_name",
        lambda *_a, **_k: "free",
    )
    store = OpenAICompatRateLimiter(db=MagicMock(), client=_BrokenRedis())
    decision = store.check(uuid.uuid4(), scope="completions")
    assert decision.allowed is True


@pytest.mark.unit
def test_idempotency_fail_open_proceeds(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.idempotency.settings.OPENAI_COMPAT_IDEMPOTENCY_ENABLED",
        True,
        raising=False,
    )
    store = IdempotencyStore(client=_BrokenRedis())
    company_id = uuid.uuid4()
    body_hash = hash_completion_body(
        {
            "company_id": str(company_id),
            "model": "m",
            "messages": [{"role": "user", "content": "x"}],
            "stream": False,
        }
    )
    action, record = store.begin_or_lookup(
        company_id=company_id,
        idempotency_key="w4-redis-down",
        request_hash=body_hash,
    )
    assert action == "proceed"
    assert record is None
