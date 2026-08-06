from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.auth.dependencies import get_current_user_and_company
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.agent_platform.schemas import (
    AgentCreate,
    AgentDeleteImpact,
    AgentDeleteRequest,
    AgentDeleteResponse,
    AgentResponse,
)
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.publish.service import PublishService
from app.agent_platform.publish.schemas import PublishResponse, AgentApiKeyCreatedResponse
from app.agent_platform.lifecycle import AgentLifecycleService, RETENTION_DAYS
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/v2/agents", tags=["Agent Platform"])


def _require_agents_delete(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.AGENTS_DELETE)(user.role)
    return user


@router.post("", response_model=AgentResponse)
def create_agent(
    agent_in: AgentCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    current_count = (
        db.query(AgentConfig)
        .filter(AgentConfig.company_id == company_id, AgentConfig.deleted_at.is_(None))
        .count()
    )
    try:
        from app.usage.dimensions import UsageDimension
        from app.usage.service import UsageService

        UsageService(db).check_quota(
            company_id, UsageDimension.AGENTS_COUNT, quantity=current_count + 1
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Quota service unavailable; agent creation blocked until metering recovers.",
        ) from exc

    new_agent = AgentConfig(
        company_id=company_id,
        name=agent_in.name,
        description=agent_in.description,
        system_prompt_template=agent_in.system_prompt_template,
        temperature=agent_in.temperature,
        is_template=agent_in.is_template,
        web_config=agent_in.web_config,
        status="DRAFT",
        version=1
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)
    try:
        from app.usage.dimensions import UsageDimension
        from app.usage.service import UsageService

        UsageService(db).record(
            company_id,
            UsageDimension.AGENTS_COUNT,
            current_count + 1,
            agent_id=new_agent.id,
            source="agent_create",
        )
    except Exception:
        # Metering lag is non-fatal after create; quota already enforced above.
        pass
    return new_agent

@router.get("", response_model=List[AgentResponse])
def list_agents(
    is_template: bool = False,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    query = (
        db.query(AgentConfig)
        .filter(AgentConfig.company_id == company_id, AgentConfig.deleted_at.is_(None))
        .order_by(AgentConfig.created_at.desc())
    )
    if is_template:
        query = query.filter(AgentConfig.is_template == True)
    return query.all()

@router.get("/templates", response_model=List[AgentResponse])
def list_templates(
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    _ = auth_data  # JWT required; templates are platform-wide, not tenant-filtered
    return (
        db.query(AgentConfig)
        .filter(AgentConfig.is_template == True, AgentConfig.deleted_at.is_(None))
        .all()
    )

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    agent = (
        db.query(AgentConfig)
        .filter(
            AgentConfig.id == agent_id,
            AgentConfig.company_id == company_id,
            AgentConfig.deleted_at.is_(None),
        )
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{agent_id}/delete-impact", response_model=AgentDeleteImpact)
def get_delete_impact(
    agent_id: UUID,
    db: Session = Depends(get_db),
    user: UserProfileResponse = Depends(_require_agents_delete),
):
    agent = AgentLifecycleService(db).get_active(agent_id, UUID(str(user.company_id)))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentDeleteImpact(**AgentLifecycleService(db).delete_impact(agent))


@router.delete("/{agent_id}", response_model=AgentDeleteResponse)
def delete_agent(
    agent_id: UUID,
    request: Request,
    body: AgentDeleteRequest = Body(default_factory=AgentDeleteRequest),
    db: Session = Depends(get_db),
    user: UserProfileResponse = Depends(_require_agents_delete),
):
    """Soft-delete an agent. Permanent cleanup runs after the retention window."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    agent = AgentLifecycleService(db).soft_delete(
        agent_id=agent_id,
        company_id=UUID(str(user.company_id)),
        user_id=UUID(str(user.id)),
        keep_conversations=body.keep_conversations,
        keep_knowledge=body.keep_knowledge,
        reason=body.reason,
        confirm_unpublish=body.confirm_unpublish,
        ip_address=ip,
        user_agent=ua,
    )
    return AgentDeleteResponse(
        id=agent.id,
        status=agent.status,
        deleted_at=agent.deleted_at,
        retention_days=RETENTION_DAYS,
        message=(
            f"Agent soft-deleted. Permanent cleanup after {RETENTION_DAYS} days "
            "unless restored by a Super Admin."
        ),
    )

@router.post("/{agent_id}/publish", response_model=PublishResponse)
def publish_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    """Backward-compatible publish — prefer /api/v1/agents/{id}/publish for RBAC."""
    service = PublishService(db)
    return service.publish(
        agent_id,
        UUID(str(auth_data["company_id"])),
        UUID(str(auth_data["user_id"])),
    )

@router.post("/{agent_id}/unpublish")
def unpublish_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = PublishService(db)
    return service.unpublish(
        agent_id,
        UUID(str(auth_data["company_id"])),
        UUID(str(auth_data["user_id"])),
    )

@router.post("/{agent_id}/clone", response_model=AgentResponse)
def clone_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    source_agent = (
        db.query(AgentConfig)
        .filter(AgentConfig.id == agent_id, AgentConfig.deleted_at.is_(None))
        .first()
    )
    if not source_agent:
        raise HTTPException(status_code=404, detail="Source agent not found")
        
    cloned = AgentConfig(
        company_id=company_id,
        name=f"Copy of {source_agent.name}",
        description=source_agent.description,
        system_prompt_template=source_agent.system_prompt_template,
        temperature=source_agent.temperature,
        web_config=source_agent.web_config,
        status="DRAFT",
        version=1,
        is_template=False
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    return cloned

@router.post("/{agent_id}/api-keys", response_model=AgentApiKeyCreatedResponse)
def generate_api_key(
    agent_id: UUID,
    name: str = "Default Key",
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = PublishService(db)
    return service.create_api_key(
        agent_id,
        UUID(str(auth_data["company_id"])),
        name=name,
    )
