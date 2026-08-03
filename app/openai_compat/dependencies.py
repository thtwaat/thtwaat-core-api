"""Auth principal for OpenAI-compatible /v1 endpoints."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.database import get_db


@dataclass(frozen=True)
class CompletionsPrincipal:
    company_id: UUID
    api_key_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    auth_kind: Literal["agent_key", "company_key"] = "agent_key"
    app_label: Optional[str] = None


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    x_key = request.headers.get("X-API-Key")
    if x_key and x_key.strip():
        return x_key.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "message": "Missing API key. Use Authorization: Bearer tht_live_... or tht_key_...",
                "type": "invalid_request_error",
                "code": "missing_api_key",
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_company_key(raw_key: str, db: Session) -> CompletionsPrincipal:
    from app.api_keys.service import APIKeyService

    service = APIKeyService(db)
    keys = service.repo.get_all_active()
    for k in keys:
        if service._verify_key(raw_key, k.key_hash):
            service.repo.update_last_used(k)
            return CompletionsPrincipal(
                company_id=k.company_id if isinstance(k.company_id, UUID) else UUID(str(k.company_id)),
                api_key_id=k.id if isinstance(k.id, UUID) else UUID(str(k.id)),
                auth_kind="company_key",
                app_label=k.app_label,
            )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "message": "Invalid API key",
                "type": "invalid_request_error",
                "code": "invalid_api_key",
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def resolve_completions_principal(
    request: Request,
    db: Session = Depends(get_db),
) -> CompletionsPrincipal:
    """Accept agent live keys (tht_*) or company platform keys (tht_key_*)."""
    raw = _extract_bearer(request)

    if raw.startswith("tht_key_"):
        return _resolve_company_key(raw, db)

    if raw.startswith("tht_"):
        from app.agent_platform.dependencies import verify_api_key_from_value

        agent_key = verify_api_key_from_value(raw, db)
        return CompletionsPrincipal(
            company_id=agent_key.company_id,
            api_key_id=agent_key.id,
            agent_id=agent_key.agent_id,
            auth_kind="agent_key",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "message": "Invalid API key format. Expected tht_live_... or tht_key_...",
                "type": "invalid_request_error",
                "code": "invalid_api_key",
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )
