"""Admin agent lifecycle — restore soft-deleted agents (Super Admin only)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.agent_platform.lifecycle import AgentLifecycleService
from app.agent_platform.schemas import AgentRestoreRequest, AgentRestoreResponse
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/v2/admin/agents", tags=["Agent Admin"])


def _require_platform_admin(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.PLATFORM_ADMIN)(user.role)
    return user


@router.post(
    "/{agent_id}/restore",
    response_model=AgentRestoreResponse,
    summary="Restore a soft-deleted agent within the retention window",
)
def restore_agent(
    agent_id: UUID,
    request: Request,
    body: AgentRestoreRequest | None = None,
    user: UserProfileResponse = Depends(_require_platform_admin),
    db: Session = Depends(get_db),
):
    body = body or AgentRestoreRequest()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    agent = AgentLifecycleService(db).restore(
        agent_id=agent_id,
        actor_user_id=UUID(str(user.id)),
        ip_address=ip,
        user_agent=ua,
        reason=body.reason,
    )
    return AgentRestoreResponse(
        id=agent.id,
        status=agent.status,
        company_id=agent.company_id,
        message="Agent restored",
    )
