"""
app/coding_agent/router.py — Phase 6C-1 (service-token minting) and
Phase 6C-2 (task-creation proxy).

    POST /api/v1/coding-agent/service-token   — Phase 6C-1.
    POST /api/v1/coding-agent/tasks            — Phase 6C-2: create a
                                                 coding task.
    GET  /api/v1/coding-agent/tasks/{task_id}   — Phase 6C-2: read status.
    POST /api/v1/coding-agent/tasks/{task_id}/cancel — Phase 6C-2: cancel.

Every route is gated by the SAME auth + RBAC every other Core endpoint
uses (app.auth.router.get_current_user + app.rbac.dependencies.
RequirePermission) — Core remains the sole user-facing authentication
and authorization boundary; company_id/user_id are taken ONLY from the
verified Core session (never from the request body), then forwarded to
AI_Project inside a fresh, short-lived service token per call
(app.coding_agent.client). AI_Project itself derives the workspace only
from that verified identity's ServiceLinkStore mapping — Core never
tells it which project/directory to use.

Idempotency reuses the EXISTING Idempotency-Key header convention this
repo already established for app/openai_compat (same header name, same
validate_idempotency_key() validator) rather than inventing a second
one; the actual dedup guarantee is enforced by AI_Project's own
service_task_idempotency store (Phase 6C-2's task infrastructure is not
duplicated here — Core only validates the key's shape and passes it
through).

Explicitly out of scope: no GitHub write, no preview deployment, no
billing, and no changes anywhere under ai/ (AgentRuntime/tools/
providers — that entire subsystem lives in the separate AI_Project
repository and is untouched by this module).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.coding_agent import client as coding_agent_client
from app.coding_agent.client import CodingAgentError
from app.coding_agent.schemas import (
    CodingTaskCancelResponse,
    CodingTaskCreateRequest,
    CodingTaskResponse,
    ServiceTokenResponse,
)
from app.coding_agent.service import mint_service_token
from app.openai_compat.idempotency import validate_idempotency_key
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/coding-agent", tags=["Coding Agent"])


def require_coding_agent_access(
    user: UserProfileResponse = Depends(get_current_user),
) -> UserProfileResponse:
    RequirePermission(Permission.CODING_AGENT_ACCESS)(user.role)
    return user


def _raise_for(exc: CodingAgentError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from None


def _to_task_response(data: dict) -> CodingTaskResponse:
    return CodingTaskResponse(
        task_id=data["task_id"], status=data["status"], phase=data.get("phase"),
        termination_code=data.get("termination_code"), created_at=data["created_at"],
        updated_at=data["updated_at"], started_at=data.get("started_at"),
        ended_at=data.get("ended_at"), result=data.get("result"), error=data.get("error"),
    )


@router.post("/service-token", response_model=ServiceTokenResponse)
def issue_service_token(
    user: UserProfileResponse = Depends(require_coding_agent_access),
) -> ServiceTokenResponse:
    result = mint_service_token(company_id=user.company_id, user_id=user.id)
    return ServiceTokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
        scope=result.scope,
    )


@router.post("/tasks", response_model=CodingTaskResponse, status_code=201)
def create_coding_task(
    payload: CodingTaskCreateRequest,
    idempotency_key: str = Header(default=None, alias="Idempotency-Key"),
    user: UserProfileResponse = Depends(require_coding_agent_access),
) -> CodingTaskResponse:
    # Same optional-header UX app.openai_compat's own completions
    # endpoint already established: a caller that supplies one gets
    # retry-safe dedup (enforced on AI_Project's side); a caller that
    # doesn't gets a fresh key generated here, so AI_Project's own
    # idempotency store always has a concrete value to key on, but this
    # single request has no cross-retry protection at Core's boundary
    # (that protection is only ever as strong as the caller reusing the
    # same header value on its own retry).
    key = validate_idempotency_key(idempotency_key) if idempotency_key is not None else str(uuid.uuid4())

    try:
        data = coding_agent_client.create_task(
            company_id=user.company_id, user_id=user.id, goal=payload.goal,
            idempotency_key=key,
            budget=payload.budget.model_dump(exclude_none=True) if payload.budget else None,
        )
    except CodingAgentError as exc:
        _raise_for(exc)
    return _to_task_response(data)


@router.get("/tasks/{task_id}", response_model=CodingTaskResponse)
def get_coding_task(
    task_id: str,
    user: UserProfileResponse = Depends(require_coding_agent_access),
) -> CodingTaskResponse:
    try:
        data = coding_agent_client.get_task(company_id=user.company_id, user_id=user.id, task_id=task_id)
    except CodingAgentError as exc:
        _raise_for(exc)
    return _to_task_response(data)


@router.post("/tasks/{task_id}/cancel", response_model=CodingTaskCancelResponse)
def cancel_coding_task(
    task_id: str,
    user: UserProfileResponse = Depends(require_coding_agent_access),
) -> CodingTaskCancelResponse:
    try:
        data = coding_agent_client.cancel_task(company_id=user.company_id, user_id=user.id, task_id=task_id)
    except CodingAgentError as exc:
        _raise_for(exc)
    return CodingTaskCancelResponse(
        task_id=data["task_id"], status=data["status"],
        cancel_requested=data["cancel_requested"], message=data["message"],
    )
