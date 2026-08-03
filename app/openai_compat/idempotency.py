"""Idempotency-Key store for OpenAI-compatible completions (Week 2 Day 3)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.config.settings import settings
from app.openai_compat.cache import fingerprint_completion_request, get_redis_client

logger = logging.getLogger(__name__)

_PREFIX = "tht:oai:idem"
_KEY_RE = re.compile(r"^[\w.:\-/=+]{1,256}$")

IdemStatus = Literal["in_progress", "completed"]


@dataclass
class IdempotencyRecord:
    status: IdemStatus
    request_hash: str
    response: Optional[dict[str, Any]] = None
    http_status: int = 200


def idempotency_redis_key(company_id: UUID | str, raw_key: str) -> str:
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"{_PREFIX}:{company_id}:{digest}"


def validate_idempotency_key(raw: str) -> str:
    key = (raw or "").strip()
    if not key or not _KEY_RE.match(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": (
                        "Invalid Idempotency-Key. Use 1–256 chars: "
                        "letters, digits, _ . : - / = +"
                    ),
                    "type": "invalid_request_error",
                    "code": "invalid_idempotency_key",
                }
            },
        )
    return key


def hash_completion_body(body_payload: dict[str, Any]) -> str:
    return fingerprint_completion_request(body_payload)


class IdempotencyStore:
    """Redis-backed idempotency for POST /v1/chat/completions."""

    def __init__(self, client: Any = None):
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "OPENAI_COMPAT_IDEMPOTENCY_ENABLED", True))

    @property
    def ttl(self) -> int:
        return int(getattr(settings, "OPENAI_COMPAT_IDEMPOTENCY_TTL_SECONDS", 86400) or 86400)

    def _redis(self):
        return self._client if self._client is not None else get_redis_client()

    def _load(self, redis_key: str) -> Optional[IdempotencyRecord]:
        try:
            raw = self._redis().get(redis_key)
            if not raw:
                return None
            data = json.loads(raw)
            return IdempotencyRecord(
                status=data["status"],
                request_hash=data["request_hash"],
                response=data.get("response"),
                http_status=int(data.get("http_status") or 200),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("idempotency load failed key=%s err=%s", redis_key, exc)
            return None

    def _save(self, redis_key: str, record: IdempotencyRecord, *, nx: bool = False) -> bool:
        payload = json.dumps(
            {
                "status": record.status,
                "request_hash": record.request_hash,
                "response": record.response,
                "http_status": record.http_status,
            },
            default=str,
        )
        try:
            r = self._redis()
            if nx:
                ok = r.set(redis_key, payload, ex=self.ttl, nx=True)
                return bool(ok)
            r.set(redis_key, payload, ex=self.ttl)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("idempotency save failed key=%s err=%s", redis_key, exc)
            return False

    def begin_or_lookup(
        self,
        *,
        company_id: UUID | str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[Literal["proceed", "replay"], Optional[IdempotencyRecord]]:
        """
        Returns:
          ("replay", record) — safe to return stored response
          ("proceed", None) — caller owns the key and should execute
        Raises HTTPException on conflict / in-progress.
        """
        if not self.enabled:
            return "proceed", None

        redis_key = idempotency_redis_key(company_id, idempotency_key)
        existing = self._load(redis_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "message": (
                                "Idempotency-Key was already used with a different request body."
                            ),
                            "type": "invalid_request_error",
                            "code": "idempotency_key_reuse",
                        }
                    },
                )
            if existing.status == "completed" and existing.response is not None:
                return "replay", existing
            if existing.status == "in_progress":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "message": (
                                "A request with this Idempotency-Key is already in progress. "
                                "Retry after the original completes."
                            ),
                            "type": "invalid_request_error",
                            "code": "idempotency_in_progress",
                        }
                    },
                )

        claimed = self._save(
            redis_key,
            IdempotencyRecord(status="in_progress", request_hash=request_hash),
            nx=True,
        )
        if claimed:
            return "proceed", None

        # Lost race — re-read
        existing = self._load(redis_key)
        if existing and existing.request_hash == request_hash:
            if existing.status == "completed" and existing.response is not None:
                return "replay", existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "message": (
                            "A request with this Idempotency-Key is already in progress. "
                            "Retry after the original completes."
                        ),
                        "type": "invalid_request_error",
                        "code": "idempotency_in_progress",
                    }
                },
            )
        if existing and existing.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "message": (
                            "Idempotency-Key was already used with a different request body."
                        ),
                        "type": "invalid_request_error",
                        "code": "idempotency_key_reuse",
                    }
                },
            )
        # Soft-fail: Redis flaky — proceed without idempotency
        logger.warning("idempotency claim failed; proceeding without lock company=%s", company_id)
        return "proceed", None

    def complete(
        self,
        *,
        company_id: UUID | str,
        idempotency_key: str,
        request_hash: str,
        response: dict[str, Any],
        http_status: int = 200,
    ) -> None:
        if not self.enabled:
            return
        redis_key = idempotency_redis_key(company_id, idempotency_key)
        self._save(
            redis_key,
            IdempotencyRecord(
                status="completed",
                request_hash=request_hash,
                response=response,
                http_status=http_status,
            ),
            nx=False,
        )

    def abandon(
        self,
        *,
        company_id: UUID | str,
        idempotency_key: str,
    ) -> None:
        """Release in-progress lock so the client can retry after a hard failure."""
        if not self.enabled:
            return
        redis_key = idempotency_redis_key(company_id, idempotency_key)
        try:
            self._redis().delete(redis_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("idempotency abandon failed key=%s err=%s", redis_key, exc)
