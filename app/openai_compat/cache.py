"""Redis caching for OpenAI-compatible /v1 surface (Week 2 Day 2)."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Optional
from uuid import UUID

from app.config.settings import settings

logger = logging.getLogger(__name__)

_PREFIX = "tht:oai"
_redis_factory: Optional[Callable[[], Any]] = None
_test_client: Any = None


def set_redis_client_for_tests(client: Any) -> None:
    """Inject fakeredis (or None to clear) for unit tests."""
    global _test_client
    _test_client = client


def _default_redis():
    import redis

    return redis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )


def get_redis_client():
    if _test_client is not None:
        return _test_client
    if _redis_factory is not None:
        return _redis_factory()
    return _default_redis()


def models_list_key(company_id: UUID | str) -> str:
    return f"{_PREFIX}:models:{company_id}"


def model_item_key(company_id: UUID | str, model_id: str) -> str:
    safe = model_id.replace(":", "_")
    return f"{_PREFIX}:model:{company_id}:{safe}"


def completion_key(company_id: UUID | str, fingerprint: str) -> str:
    return f"{_PREFIX}:cmpl:{company_id}:{fingerprint}"


def fingerprint_completion_request(payload: dict[str, Any]) -> str:
    """Stable hash for deterministic (temperature=0) completion reuse."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class OpenAICompatCache:
    """Tenant-scoped model metadata + optional completion response cache."""

    def __init__(self, client: Any = None):
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "OPENAI_COMPAT_CACHE_ENABLED", True))

    @property
    def model_ttl(self) -> int:
        return int(getattr(settings, "OPENAI_COMPAT_MODEL_CACHE_TTL_SECONDS", 300) or 300)

    @property
    def response_ttl(self) -> int:
        return int(getattr(settings, "OPENAI_COMPAT_RESPONSE_CACHE_TTL_SECONDS", 60) or 60)

    @property
    def responses_enabled(self) -> bool:
        return bool(getattr(settings, "OPENAI_COMPAT_CACHE_RESPONSES", True))

    def _redis(self):
        return self._client if self._client is not None else get_redis_client()

    def get_json(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        try:
            raw = self._redis().get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_compat cache get failed key=%s err=%s", key, exc)
            return None

    def set_json(self, key: str, value: Any, *, ttl: int) -> bool:
        if not self.enabled or ttl <= 0:
            return False
        try:
            self._redis().setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_compat cache set failed key=%s err=%s", key, exc)
            return False

    def delete(self, key: str) -> None:
        try:
            self._redis().delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_compat cache delete failed key=%s err=%s", key, exc)

    def _delete_pattern(self, pattern: str) -> int:
        deleted = 0
        try:
            r = self._redis()
            # SCAN-friendly; works with fakeredis and production Redis
            for key in r.scan_iter(match=pattern, count=100):
                r.delete(key)
                deleted += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_compat cache scan/delete failed pattern=%s err=%s", pattern, exc)
        return deleted

    def get_models_list(self, company_id: UUID | str) -> Optional[dict]:
        return self.get_json(models_list_key(company_id))

    def set_models_list(self, company_id: UUID | str, payload: dict) -> bool:
        return self.set_json(models_list_key(company_id), payload, ttl=self.model_ttl)

    def get_model(self, company_id: UUID | str, model_id: str) -> Optional[dict]:
        return self.get_json(model_item_key(company_id, model_id))

    def set_model(self, company_id: UUID | str, model_id: str, payload: dict) -> bool:
        return self.set_json(model_item_key(company_id, model_id), payload, ttl=self.model_ttl)

    def get_completion(self, company_id: UUID | str, fingerprint: str) -> Optional[dict]:
        if not self.responses_enabled:
            return None
        return self.get_json(completion_key(company_id, fingerprint))

    def set_completion(self, company_id: UUID | str, fingerprint: str, payload: dict) -> bool:
        if not self.responses_enabled:
            return False
        return self.set_json(
            completion_key(company_id, fingerprint),
            payload,
            ttl=self.response_ttl,
        )

    def invalidate_models(self, company_id: UUID | str) -> int:
        n = 0
        self.delete(models_list_key(company_id))
        n += 1
        n += self._delete_pattern(f"{_PREFIX}:model:{company_id}:*")
        return n

    def invalidate_responses(self, company_id: UUID | str) -> int:
        return self._delete_pattern(f"{_PREFIX}:cmpl:{company_id}:*")

    def invalidate_all(self, company_id: UUID | str) -> int:
        return self.invalidate_models(company_id) + self.invalidate_responses(company_id)
