"""Retry & timeout policies for enterprise gateway calls."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

from app.config.settings import settings

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    backoff_ms: int = 200
    timeout_seconds: float = 60.0

    @classmethod
    def from_settings(cls) -> "RetryPolicy":
        return cls(
            max_attempts=max(1, int(getattr(settings, "GATEWAY_RETRY_MAX_ATTEMPTS", 2) or 2)),
            backoff_ms=max(0, int(getattr(settings, "GATEWAY_RETRY_BACKOFF_MS", 200) or 0)),
            timeout_seconds=float(getattr(settings, "GATEWAY_REQUEST_TIMEOUT_SECONDS", 60.0) or 60.0),
        )


async def with_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    policy: Optional[RetryPolicy] = None,
    retry_on: tuple = (Exception,),
) -> T:
    """Run async factory with timeout + limited retries (no retry after success)."""
    pol = policy or RetryPolicy.from_settings()
    last_exc: Optional[BaseException] = None
    attempts = max(1, pol.max_attempts)
    for i in range(attempts):
        try:
            return await asyncio.wait_for(factory(), timeout=pol.timeout_seconds)
        except retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            if i >= attempts - 1:
                break
            if pol.backoff_ms:
                await asyncio.sleep(pol.backoff_ms / 1000.0)
    assert last_exc is not None
    raise last_exc
