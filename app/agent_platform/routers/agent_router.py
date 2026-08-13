from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.auth.dependencies import get_current_user_and_company
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.agent_platform.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentChatUsage,
    AgentCreate,
    AgentDeleteImpact,
    AgentDeleteRequest,
    AgentDeleteResponse,
    AgentResponse,
    AgentToolInfo,
    AgentUpdate,
)
from app.agent_platform.agent_runtime import slugify
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.protection import is_protected_agent
from app.agent_platform.publish.service import PublishService
from app.agent_platform.publish.schemas import PublishResponse, AgentApiKeyCreatedResponse
from app.agent_platform.lifecycle import AgentLifecycleService, RETENTION_DAYS
from app.agent_platform.services.conversation_service import ConversationService
from app.agent_platform.registries.tool_registry import ToolRegistry
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/v2/agents", tags=["Agent Platform"])


def _require_agents_delete(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.AGENTS_DELETE)(user.role)
    return user


def _require_agents_update(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.AGENTS_UPDATE)(user.role)
    return user


def _require_agents_create(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.AGENTS_CREATE)(user.role)
    return user


def _require_agents_read(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.AGENTS_READ)(user.role)
    return user


def _require_agents_publish(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.AGENTS_PUBLISH)(user.role)
    return user


def _require_agents_manage_keys(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.AGENTS_MANAGE_KEYS)(user.role)
    return user


def _unique_slug(db: Session, company_id, name: str, agent_id=None) -> str:
    base = slugify(name, "agent")
    query = db.query(AgentConfig.slug).filter(AgentConfig.company_id == company_id)
    if agent_id is not None:
        query = query.filter(AgentConfig.id != agent_id)
    existing = {row[0] for row in query if row[0]}
    slug = base
    suffix = 1
    while slug in existing:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


@router.post("", response_model=AgentResponse)
def create_agent(
    agent_in: AgentCreate,
    db: Session = Depends(get_db),
    user: UserProfileResponse = Depends(_require_agents_create),
):
    company_id = UUID(str(user.company_id))
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

    resolved_slug = agent_in.slug or _unique_slug(db, company_id, agent_in.name)
    # Protected production agents (e.g. Viral Awaaz) must never be created as templates.
    is_template = bool(agent_in.is_template)
    if is_template and is_protected_agent(name=agent_in.name, slug=resolved_slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Protected production agents cannot be created as reusable templates.",
        )

    new_agent = AgentConfig(
        company_id=company_id,
        name=agent_in.name,
        slug=resolved_slug,
        description=agent_in.description,
        system_prompt_template=agent_in.system_prompt_template,
        provider=agent_in.provider,
        model=agent_in.model,
        temperature=agent_in.temperature,
        is_template=is_template,
        allowed_tools=agent_in.allowed_tools,
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
    user: UserProfileResponse = Depends(_require_agents_read),
):
    company_id = UUID(str(user.company_id))
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
    templates = (
        db.query(AgentConfig)
        .filter(AgentConfig.is_template == True, AgentConfig.deleted_at.is_(None))
        .all()
    )
    # Never expose protected production agents (Viral Awaaz) as reusable templates.
    return [a for a in templates if not is_protected_agent(agent=a)]

@router.get("/tools", response_model=List[AgentToolInfo])
def list_available_tools(
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Registered tool capabilities agents can be granted via allowed_tools."""
    _ = auth_data  # JWT required; the tool catalog itself is platform-wide
    return [
        AgentToolInfo(name=name, description=ToolRegistry.get_tool(name).description)
        for name in ToolRegistry.list_tools()
    ]

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


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: UUID,
    patch: AgentUpdate,
    db: Session = Depends(get_db),
    user: UserProfileResponse = Depends(_require_agents_update),
):
    """Edit an existing agent's configuration (instructions, provider/model, tools, ...)."""
    company_id = UUID(str(user.company_id))
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

    updates = patch.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(agent, field, value)

    db.add(agent)
    db.commit()
    db.refresh(agent)
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
    user: UserProfileResponse = Depends(_require_agents_publish),
):
    """Backward-compatible publish — prefer /api/v1/agents/{id}/publish for RBAC."""
    service = PublishService(db)
    return service.publish(
        agent_id,
        UUID(str(user.company_id)),
        UUID(str(user.id)),
    )

@router.post("/{agent_id}/unpublish")
def unpublish_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    user: UserProfileResponse = Depends(_require_agents_publish),
):
    service = PublishService(db)
    return service.unpublish(
        agent_id,
        UUID(str(user.company_id)),
        UUID(str(user.id)),
    )

@router.post("/{agent_id}/clone", response_model=AgentResponse)
def clone_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    user: UserProfileResponse = Depends(_require_agents_create),
):
    company_id = UUID(str(user.company_id))
    source_agent = (
        db.query(AgentConfig)
        .filter(
            AgentConfig.id == agent_id,
            AgentConfig.deleted_at.is_(None),
        )
        .filter(
            (AgentConfig.company_id == company_id) | (AgentConfig.is_template == True)
        )
        .first()
    )
    if not source_agent:
        raise HTTPException(status_code=404, detail="Source agent not found")

    # Protected production agents may be cloned within their own company only —
    # never reused cross-tenant via the template path.
    if is_protected_agent(agent=source_agent) and source_agent.company_id != company_id:
        raise HTTPException(status_code=404, detail="Source agent not found")

    cloned_name = f"Copy of {source_agent.name}"
    cloned = AgentConfig(
        company_id=company_id,
        name=cloned_name,
        slug=_unique_slug(db, company_id, cloned_name),
        description=source_agent.description,
        system_prompt_template=source_agent.system_prompt_template,
        provider=source_agent.provider,
        model=source_agent.model,
        temperature=source_agent.temperature,
        allowed_tools=list(source_agent.allowed_tools or []),
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
    user: UserProfileResponse = Depends(_require_agents_manage_keys),
):
    service = PublishService(db)
    return service.create_api_key(
        agent_id,
        UUID(str(user.company_id)),
        name=name,
    )


@router.post("/{agent_id}/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    agent_id: UUID,
    body: AgentChatRequest,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Single-shot authenticated chat. Auto-creates a dashboard conversation when
    conversation_id is omitted; otherwise continues an existing one. A thin wrapper
    around ConversationService — no separate runtime."""
    from app.agent_platform.conversation_schemas import ConversationCreate

    company_id = UUID(str(auth_data["company_id"]))
    user_id = auth_data.get("user_id")

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

    conversation_id = body.conversation_id
    if not conversation_id:
        conv = ConversationService.create_conversation(
            db,
            company_id,
            ConversationCreate(agent_id=agent_id, title="Chat", channel="dashboard"),
        )
        conversation_id = conv.id

    result = await ConversationService.send_message(
        db,
        conversation_id,
        company_id,
        body.message,
        actor_user_id=UUID(str(user_id)) if user_id else None,
    )
    assistant = result.get("assistant_message")
    usage = result.get("usage") or {}
    return AgentChatResponse(
        message=assistant.content if assistant else "",
        conversation_id=conversation_id,
        usage=AgentChatUsage(**usage),
    )
