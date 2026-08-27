"""
app/coding_agent/service.py — Phase 6C-1: mints short-lived, scoped
service tokens Core issues so the separately-deployed Coding AI /
AgentRuntime platform (dashboard.thtwaat.com, E:\\AI_Project) can trust a
request as coming from a specific, already-authenticated Core
(company_id, user_id) — WITHOUT that platform ever seeing this user's
Core session JWT, password, or any Core secret beyond the one shared
signing key.

Reuses the HS256 JWT machinery this repo already depends on
(python-jose, the same library app.auth.service uses for user JWTs)
rather than inventing a second token format. Signs with its OWN secret
(settings.CODING_AGENT_SERVICE_JWT_SECRET), never JWT_SECRET_KEY /
JWT_REFRESH_SECRET_KEY — a leaked/rotated service secret must never be
able to forge a user session, and vice versa.

Minting is a pure, stateless function: it does not call AI_Project over
the network and does not persist anything. Phase 6C-1 explicitly stops
here — proxying an actual task-creation/task-status call through to
AI_Project is a later phase, not this one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from fastapi import HTTPException, status
from jose import jwt

from app.config.settings import settings

ALGORITHM = "HS256"
DEFAULT_SCOPES: tuple[str, ...] = ("coding_agent:access",)


@dataclass(frozen=True)
class ServiceTokenResult:
    access_token: str
    token_type: str
    expires_in: int
    scope: str


def mint_service_token(
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    scopes: Sequence[str] = DEFAULT_SCOPES,
) -> ServiceTokenResult:
    """Mint a short-lived HS256 token identifying (company_id, user_id) to
    AI_Project. Fails closed (503) rather than issuing an unsigned/
    unconfigured token if the operator has not yet set
    CODING_AGENT_SERVICE_JWT_SECRET — there is no insecure fallback."""
    secret = settings.CODING_AGENT_SERVICE_JWT_SECRET
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Coding Agent integration is not configured on this server.",
        )

    ttl_seconds = int(settings.CODING_AGENT_SERVICE_TOKEN_TTL_SECONDS)
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=ttl_seconds)
    scope_str = " ".join(scopes)

    claims = {
        "iss": settings.CODING_AGENT_JWT_ISSUER,
        "aud": settings.CODING_AGENT_JWT_AUDIENCE,
        "sub": str(user_id),
        "company_id": str(company_id),
        "user_id": str(user_id),
        "scope": scope_str,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(claims, secret, algorithm=ALGORITHM)
    return ServiceTokenResult(
        access_token=token,
        token_type="bearer",
        expires_in=ttl_seconds,
        scope=scope_str,
    )
