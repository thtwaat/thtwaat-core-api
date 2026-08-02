"""Short-lived signed tokens for iframe widget embeds (no live API keys in URLs)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config.settings import settings

EMBED_TOKEN_PREFIX = "tht_embed_"
EMBED_TOKEN_TYP = "widget_embed"
DEFAULT_EMBED_TTL_SECONDS = 3600
ALGORITHM = "HS256"


def embed_token_ttl_seconds() -> int:
    return int(getattr(settings, "EMBED_TOKEN_TTL_SECONDS", DEFAULT_EMBED_TTL_SECONDS) or DEFAULT_EMBED_TTL_SECONDS)


def mint_embed_token(
    *,
    widget_id: str,
    agent_id: UUID | str,
    company_id: UUID | str,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> str:
    """Return a signed JWT (without the tht_embed_ prefix)."""
    if not widget_id:
        raise ValueError("widget_id is required")
    ttl = DEFAULT_EMBED_TTL_SECONDS if ttl_seconds is None else int(ttl_seconds)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")
    issued = now or datetime.now(timezone.utc)
    payload = {
        "typ": EMBED_TOKEN_TYP,
        "wid": widget_id,
        "aid": str(agent_id),
        "cid": str(company_id),
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def format_embed_credential(raw_jwt: str) -> str:
    if raw_jwt.startswith(EMBED_TOKEN_PREFIX):
        return raw_jwt
    return f"{EMBED_TOKEN_PREFIX}{raw_jwt}"


def parse_embed_credential(raw: str) -> str | None:
    """Return bare JWT if ``raw`` is an embed credential, else None."""
    if not raw:
        return None
    if raw.startswith(EMBED_TOKEN_PREFIX):
        return raw[len(EMBED_TOKEN_PREFIX) :]
    return None


def verify_embed_token(raw_jwt: str) -> dict[str, Any]:
    """Validate signature + expiry; return claims. Raises HTTPException on failure."""
    if not raw_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid embed token",
        )
    token = raw_jwt[len(EMBED_TOKEN_PREFIX) :] if raw_jwt.startswith(EMBED_TOKEN_PREFIX) else raw_jwt
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired embed token",
        ) from None

    if payload.get("typ") != EMBED_TOKEN_TYP:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid embed token type",
        )
    if not payload.get("wid") or not payload.get("aid") or not payload.get("cid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid embed token claims",
        )
    return payload
