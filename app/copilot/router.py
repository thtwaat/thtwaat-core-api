"""AI Copilot API routes."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.copilot.intents import TaskStatus
from app.copilot.schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmTaskRequest,
    FailureDiagnostics,
    HistoryResponse,
    TaskListResponse,
    TaskResponse,
    ToolsResponse,
)
from app.copilot.service import CopilotService
from app.database.database import get_db
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/copilot", tags=["AI Copilot"])


def get_copilot_service(db: Session = Depends(get_db)) -> CopilotService:
    return CopilotService(db)


def require_platform_admin(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.PLATFORM_ADMIN)(user.role)
    return user


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with the AI Copilot (NLU → plan → execute)",
)
def chat(
    payload: ChatRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.chat(user.company_id, user.id, user.role, payload)


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="List Copilot task execution history",
)
def list_tasks(
    status: Optional[TaskStatus] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    mine: bool = Query(True),
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.list_tasks(
        user.company_id,
        user_id=user.id if mine else None,
        status=status,
        limit=limit,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get a Copilot task with step progress",
)
def get_task(
    task_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.get_task(task_id, user.company_id)


@router.post(
    "/tasks/{task_id}/confirm",
    response_model=TaskResponse,
    summary="Confirm (or decline) a destructive Copilot task",
)
def confirm_task(
    task_id: UUID,
    payload: ConfirmTaskRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.confirm_task(task_id, user.company_id, user.id, user.role, payload)


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=TaskResponse,
    summary="Cancel a planned / running Copilot task",
)
def cancel_task(
    task_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.cancel_task(task_id, user.company_id)


@router.post(
    "/tasks/{task_id}/replay",
    response_model=TaskResponse,
    summary="Replay a previous Copilot task",
)
def replay_task(
    task_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.replay_task(task_id, user.company_id, user.id, user.role)


@router.get(
    "/tasks/{task_id}/diagnostics",
    response_model=FailureDiagnostics,
    summary="Failure diagnostics for a Copilot task",
)
def task_diagnostics(
    task_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.diagnostics(task_id, user.company_id)


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Prompt / conversation history",
)
def history(
    conversation_id: Optional[UUID] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.history(user.company_id, user.id, conversation_id, limit)


@router.get(
    "/tools",
    response_model=ToolsResponse,
    summary="List Copilot tools and workflow definitions",
)
def list_tools(
    user: UserProfileResponse = Depends(get_current_user),
    service: CopilotService = Depends(get_copilot_service),
):
    _ = user  # JWT required; tool catalog is not tenant-scoped
    return service.list_tools()


@router.get(
    "/admin/executions",
    response_model=TaskListResponse,
    summary="Admin: company-wide Copilot execution history",
)
def admin_executions(
    company_id: Optional[UUID] = Query(default=None),
    status: Optional[TaskStatus] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: CopilotService = Depends(get_copilot_service),
):
    return service.list_tasks(
        company_id or user.company_id,
        user_id=None,
        status=status,
        limit=limit,
    )
