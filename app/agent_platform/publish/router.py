"""Agent Publish API — /api/v1/agents/..."""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.agent_platform.publish.schemas import (
    AgentApiKeyCreate,
    AgentApiKeyCreatedResponse,
    AgentApiKeyListItem,
    AgentApiKeyRotateResponse,
    AgentLifecycleResponse,
    EmbedSnippetResponse,
    PublishResponse,
    UnpublishResponse,
    WidgetConfigResponse,
    WidgetConfigUpdate,
)
from app.agent_platform.publish.service import PublishService
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/agents", tags=["Agent Publish"])


def get_publish_service(db: Session = Depends(get_db)) -> PublishService:
    return PublishService(db)


def require_permission(permission: Permission):
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        RequirePermission(permission)(user.role)
        return user

    return _check


@router.post(
    "/{agent_id}/publish",
    response_model=PublishResponse,
    summary="Publish an agent for websites, apps, and SaaS",
)
def publish_agent(
    agent_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_PUBLISH)),
    service: PublishService = Depends(get_publish_service),
):
    return service.publish(agent_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.post(
    "/{agent_id}/unpublish",
    response_model=UnpublishResponse,
    summary="Unpublish an agent (status → DRAFT)",
)
def unpublish_agent(
    agent_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_PUBLISH)),
    service: PublishService = Depends(get_publish_service),
):
    return service.unpublish(agent_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.post(
    "/{agent_id}/pause",
    response_model=AgentLifecycleResponse,
    summary="Pause a live agent (stops serving chat, keeps widget/keys intact)",
)
def pause_agent(
    agent_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_PUBLISH)),
    service: PublishService = Depends(get_publish_service),
):
    return service.pause(agent_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.post(
    "/{agent_id}/resume",
    response_model=AgentLifecycleResponse,
    summary="Resume a paused agent",
)
def resume_agent(
    agent_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_PUBLISH)),
    service: PublishService = Depends(get_publish_service),
):
    return service.resume(agent_id, UUID(str(user.company_id)), UUID(str(user.id)))


@router.get(
    "/{agent_id}/api-keys",
    response_model=List[AgentApiKeyListItem],
    summary="List agent API keys",
)
def list_api_keys(
    agent_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_MANAGE_KEYS)),
    service: PublishService = Depends(get_publish_service),
):
    return service.list_api_keys(agent_id, UUID(str(user.company_id)))


@router.post(
    "/{agent_id}/api-keys",
    response_model=AgentApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new agent API key",
)
def create_api_key(
    agent_id: UUID,
    body: AgentApiKeyCreate,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_MANAGE_KEYS)),
    service: PublishService = Depends(get_publish_service),
):
    return service.create_api_key(
        agent_id,
        UUID(str(user.company_id)),
        name=body.name,
        expires_at=body.expires_at,
    )


@router.post(
    "/{agent_id}/api-keys/{key_id}/rotate",
    response_model=AgentApiKeyRotateResponse,
    summary="Rotate (revoke old + issue new) API key",
)
def rotate_api_key(
    agent_id: UUID,
    key_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_MANAGE_KEYS)),
    service: PublishService = Depends(get_publish_service),
):
    return service.rotate_api_key(agent_id, UUID(str(user.company_id)), key_id)


@router.post(
    "/{agent_id}/api-keys/{key_id}/disable",
    response_model=AgentApiKeyListItem,
    summary="Disable an API key",
)
def disable_api_key(
    agent_id: UUID,
    key_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_MANAGE_KEYS)),
    service: PublishService = Depends(get_publish_service),
):
    return service.disable_api_key(agent_id, UUID(str(user.company_id)), key_id)


@router.delete(
    "/{agent_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an API key",
)
def delete_api_key(
    agent_id: UUID,
    key_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_MANAGE_KEYS)),
    service: PublishService = Depends(get_publish_service),
):
    service.delete_api_key(agent_id, UUID(str(user.company_id)), key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{agent_id}/widget",
    response_model=WidgetConfigResponse,
    summary="Get widget / embed configuration",
)
def get_widget(
    agent_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_READ)),
    service: PublishService = Depends(get_publish_service),
):
    return service.get_widget_config(agent_id, UUID(str(user.company_id)))


@router.get(
    "/{agent_id}/embed",
    response_model=EmbedSnippetResponse,
    summary="Copy-ready script + iframe snippets for dashboard",
)
def get_embed_snippets(
    agent_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_READ)),
    service: PublishService = Depends(get_publish_service),
):
    return service.get_embed_snippets(agent_id, UUID(str(user.company_id)))


@router.patch(
    "/{agent_id}/widget",
    response_model=WidgetConfigResponse,
    summary="Update widget configuration",
)
def update_widget(
    agent_id: UUID,
    body: WidgetConfigUpdate,
    user: UserProfileResponse = Depends(require_permission(Permission.AGENTS_UPDATE)),
    service: PublishService = Depends(get_publish_service),
):
    return service.update_widget_config(agent_id, UUID(str(user.company_id)), body)
