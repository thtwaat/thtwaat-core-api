"""Customer Onboarding Wizard API routes."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.onboarding.schemas import (
    AdminSessionListResponse,
    AutosaveRequest,
    CompleteStepRequest,
    FlowDefinitionResponse,
    OnboardingAnalyticsResponse,
    OnboardingSessionResponse,
    SkipStepRequest,
    StartOnboardingRequest,
    StartOnboardingResponse,
    StepActionResponse,
)
from app.onboarding.service import OnboardingService
from app.onboarding.steps import OnboardingStatus, OnboardingStep
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/onboarding", tags=["Customer Onboarding"])


def get_onboarding_service(db: Session = Depends(get_db)) -> OnboardingService:
    return OnboardingService(db)


def require_permission(permission: Permission):
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        RequirePermission(permission)(user.role)
        return user

    return _check


# ── Public / semi-public ──────────────────────────────────────────────────────

@router.get(
    "/flow",
    response_model=FlowDefinitionResponse,
    summary="Get onboarding wizard step definition",
)
def get_flow(service: OnboardingService = Depends(get_onboarding_service)):
    return service.get_flow_definition()


@router.post(
    "/start",
    response_model=StartOnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start onboarding (create company + owner account)",
)
def start_onboarding(
    payload: StartOnboardingRequest,
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.start(payload)


@router.get(
    "/resume/{resume_token}",
    response_model=OnboardingSessionResponse,
    summary="Resume onboarding later via resume token",
)
def resume_by_token(
    resume_token: str,
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.resume_by_token(resume_token)


# ── Authenticated wizard ──────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=OnboardingSessionResponse,
    summary="Get current user's onboarding session (progress + checklist)",
)
def get_my_session(
    user: UserProfileResponse = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.get_for_user(user.id, user.company_id)


@router.post(
    "/me/autosave",
    response_model=OnboardingSessionResponse,
    summary="Auto-save draft data for the current or specified step",
)
def autosave(
    payload: AutosaveRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.autosave(user.id, user.company_id, payload)


@router.post(
    "/me/pause",
    response_model=OnboardingSessionResponse,
    summary="Pause onboarding (resume later)",
)
def pause(
    user: UserProfileResponse = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.pause(user.id, user.company_id)


@router.post(
    "/me/resume",
    response_model=OnboardingSessionResponse,
    summary="Resume a paused onboarding session",
)
def resume(
    user: UserProfileResponse = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.resume(user.id, user.company_id)


@router.post(
    "/me/steps/{step}/complete",
    response_model=StepActionResponse,
    summary="Validate and complete a wizard step (delegates to platform services)",
)
def complete_step(
    step: OnboardingStep,
    payload: CompleteStepRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.complete_step(user.id, user.company_id, step, payload)


@router.post(
    "/me/steps/{step}/skip",
    response_model=StepActionResponse,
    summary="Skip an optional wizard step",
)
def skip_step(
    step: OnboardingStep,
    payload: SkipStepRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.skip_step(user.id, user.company_id, step, payload)


@router.post(
    "/me/knowledge/upload",
    response_model=StepActionResponse,
    summary="Upload a knowledge document during onboarding (optional step helper)",
)
async def upload_knowledge(
    file: UploadFile = File(...),
    knowledge_base_id: Optional[UUID] = Query(default=None),
    user: UserProfileResponse = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return await service.upload_knowledge_file(
        user.id, user.company_id, file, knowledge_base_id
    )


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get(
    "/admin/sessions",
    response_model=AdminSessionListResponse,
    summary="Admin: list onboarding sessions",
)
def admin_list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[OnboardingStatus] = Query(default=None, alias="status"),
    company_id: Optional[UUID] = Query(default=None),
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.admin_list_sessions(page, page_size, status_filter, company_id)


@router.get(
    "/admin/sessions/{session_id}",
    response_model=OnboardingSessionResponse,
    summary="Admin: view a single onboarding session",
)
def admin_get_session(
    session_id: UUID,
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.admin_get_session(session_id)


@router.get(
    "/admin/analytics",
    response_model=OnboardingAnalyticsResponse,
    summary="Admin: completion rate and drop-off analytics",
)
def admin_analytics(
    user: UserProfileResponse = Depends(require_permission(Permission.PLATFORM_ADMIN)),
    service: OnboardingService = Depends(get_onboarding_service),
):
    return service.admin_analytics()
