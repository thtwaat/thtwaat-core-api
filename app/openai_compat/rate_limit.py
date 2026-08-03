"""Tenant/plan rate limiting for OpenAI-compatible /v1 (Week 2 Day 4)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from fastapi import HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.openai_compat.cache import get_redis_client

logger = logging.getLogger(__name__)

_PREFIX = "tht:oai:rl"
Window = Literal["rpm", "rpd"]
Scope = Literal["completions", "models"]

# Plan → {scope: {rpm, rpd}} — single source for Day 4 (settings can override RPM defaults)
DEFAULT_PLAN_RATE_LIMITS: Dict[str, Dict[str, Dict[str, int]]] = {
    "free": {
        "completions": {"rpm": 20, "rpd": 200},
        "models": {"rpm": 60, "rpd": 2_000},
    },
    "starter": {
        "completions": {"rpm": 60, "rpd": 2_000},
        "models": {"rpm": 120, "rpd": 10_000},
    },
    "growth": {
        "completions": {"rpm": 300, "rpd": 20_000},
        "models": {"rpm": 300, "rpd": 50_000},
    },
    "pro": {  # usage-tier alias → growth
        "completions": {"rpm": 300, "rpd": 20_000},
        "models": {"rpm": 300, "rpd": 50_000},
    },
    "business": {
        "completions": {"rpm": 600, "rpd": 50_000},
        "models": {"rpm": 600, "rpd": 100_000},
    },
    "enterprise": {
        "completions": {"rpm": 2_000, "rpd": 500_000},
        "models": {"rpm": 1_000, "rpd": 500_000},
    },
}


@dataclass
class RateLimitDecision:
    plan: str
    scope: Scope
    limit: int
    remaining: int
    reset_at: int
    window: Window
    allowed: bool
    retry_after: int = 0


def resolve_plan_name(db: Session, company_id: UUID) -> str:
    """Best-effort company.plan → canonical rate-limit plan key."""
    default = (getattr(settings, "OPENAI_COMPAT_RATE_LIMIT_DEFAULT_PLAN", None) or "free")
    if not isinstance(default, str):
        default = "free"
    default = default.lower()

    try:
        # Import User so Company.relationship("User") can configure in unit tests.
        from app.companies.model import Company  # noqa: WPS433
        from app.users.model import User  # noqa: F401,WPS433

        row = db.query(Company.plan).filter(Company.id == company_id).first()
        if not row:
            return default
        plan = row[0]
        name = getattr(plan, "value", plan)
        if not isinstance(name, str) or not name.strip():
            return default
        return name.strip().lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning("rate_limit plan resolve failed company=%s err=%s", company_id, exc)
        return default

def limits_for_plan(plan: str, scope: Scope) -> Dict[str, int]:
    key = (plan or "free").lower()
    table = DEFAULT_PLAN_RATE_LIMITS.get(key) or DEFAULT_PLAN_RATE_LIMITS["free"]
    scope_limits = dict(table.get(scope) or table["completions"])

    # Optional global overrides (completions only unless scoped settings added later)
    if scope == "completions":
        rpm_override = getattr(settings, "OPENAI_COMPAT_RATE_LIMIT_RPM", None)
        rpd_override = getattr(settings, "OPENAI_COMPAT_RATE_LIMIT_RPD", None)
        if rpm_override is not None:
            scope_limits["rpm"] = int(rpm_override)
        if rpd_override is not None:
            scope_limits["rpd"] = int(rpd_override)
    return scope_limits


def _window_meta(window: Window) -> tuple[int, int, int]:
    """Return (bucket_id, ttl_seconds, reset_at_epoch)."""
    now = int(time.time())
    if window == "rpm":
        bucket = now // 60
        ttl = 60 - (now % 60)
        if ttl <= 0:
            ttl = 60
        reset_at = (bucket + 1) * 60
        return bucket, ttl, reset_at
    bucket = now // 86400
    ttl = 86400 - (now % 86400)
    if ttl <= 0:
        ttl = 86400
    reset_at = (bucket + 1) * 86400
    return bucket, ttl, reset_at


def rate_limit_key(company_id: UUID | str, scope: Scope, window: Window, bucket: int) -> str:
    return f"{_PREFIX}:{scope}:{window}:{company_id}:{bucket}"


class OpenAICompatRateLimiter:
    """Fixed-window Redis counters keyed by tenant + scope."""

    def __init__(self, db: Session, client: Any = None):
        self.db = db
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "OPENAI_COMPAT_RATE_LIMIT_ENABLED", True))

    def _redis(self):
        return self._client if self._client is not None else get_redis_client()

    def check(self, company_id: UUID, *, scope: Scope = "completions") -> RateLimitDecision:
        plan = resolve_plan_name(self.db, company_id)
        limits = limits_for_plan(plan, scope)

        if not self.enabled:
            rpm = int(limits["rpm"])
            _, _, reset_at = _window_meta("rpm")
            return RateLimitDecision(
                plan=plan,
                scope=scope,
                limit=rpm,
                remaining=rpm,
                reset_at=reset_at,
                window="rpm",
                allowed=True,
            )

        # Check RPM then RPD — first violation wins
        for window in ("rpm", "rpd"):
            limit = int(limits[window])
            bucket, ttl, reset_at = _window_meta(window)
            key = rate_limit_key(company_id, scope, window, bucket)
            try:
                r = self._redis()
                count = int(r.incr(key))
                if count == 1:
                    r.expire(key, ttl)
                # Ensure TTL exists even if incr raced
                if r.ttl(key) < 0:
                    r.expire(key, ttl)
            except Exception as exc:  # noqa: BLE001 — soft-fail open
                logger.warning("rate_limit redis failed company=%s err=%s", company_id, exc)
                return RateLimitDecision(
                    plan=plan,
                    scope=scope,
                    limit=int(limits["rpm"]),
                    remaining=int(limits["rpm"]),
                    reset_at=reset_at,
                    window="rpm",
                    allowed=True,
                )

            remaining = max(0, limit - count)
            if count > limit:
                retry_after = max(1, int(r.ttl(key) if r.ttl(key) > 0 else ttl))
                return RateLimitDecision(
                    plan=plan,
                    scope=scope,
                    limit=limit,
                    remaining=0,
                    reset_at=reset_at,
                    window=window,
                    allowed=False,
                    retry_after=retry_after,
                )

        rpm_limit = int(limits["rpm"])
        _, _, rpm_reset = _window_meta("rpm")
        # Re-read remaining for headers (approx from last rpm check)
        try:
            bucket, _, _ = _window_meta("rpm")
            key = rate_limit_key(company_id, scope, "rpm", bucket)
            used = int(self._redis().get(key) or 0)
            remaining = max(0, rpm_limit - used)
        except Exception:
            remaining = rpm_limit

        return RateLimitDecision(
            plan=plan,
            scope=scope,
            limit=rpm_limit,
            remaining=remaining,
            reset_at=rpm_reset,
            window="rpm",
            allowed=True,
        )

    def enforce(self, company_id: UUID, *, scope: Scope = "completions") -> RateLimitDecision:
        decision = self.check(company_id, scope=scope)
        if decision.allowed:
            return decision
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "message": (
                        f"Rate limit exceeded for plan '{decision.plan}' ({decision.window})."
                    ),
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                    "plan": decision.plan,
                    "limit": decision.limit,
                    "window": decision.window,
                    "scope": decision.scope,
                }
            },
            headers=self.header_map(decision),
        )

    @staticmethod
    def header_map(decision: RateLimitDecision) -> Dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(int(decision.limit)),
            "X-RateLimit-Remaining": str(int(decision.remaining)),
            "X-RateLimit-Reset": str(int(decision.reset_at)),
            "X-RateLimit-Plan": str(decision.plan),
        }
        if not decision.allowed:
            headers["Retry-After"] = str(max(1, int(decision.retry_after or 1)))
        return headers
    def apply_headers(self, response: Response, decision: RateLimitDecision) -> None:
        for k, v in self.header_map(decision).items():
            if k == "Retry-After" and decision.allowed:
                continue
            response.headers[k] = v
