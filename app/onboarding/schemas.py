"""Pydantic schemas for the Customer Onboarding Wizard."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.onboarding.steps import OnboardingStatus, OnboardingStep


# ── Start / account ───────────────────────────────────────────────────────────

class AccountDraft(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class CompanyDraft(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    website: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    timezone: str = Field(default="UTC", max_length=100)


class StartOnboardingRequest(BaseModel):
    """
    Creates company + owner account, marks email verified (no OTP), issues JWTs.

    Backend requires a company_id to create a user, so company is collected
    together with the account. Step Create Company then refines the profile.
    """
    account: AccountDraft
    company: CompanyDraft
    send_welcome_email: bool = True
    # Deprecated alias — ignored (OTP verification removed).
    send_verification: bool = False


class AutosaveRequest(BaseModel):
    step: Optional[OnboardingStep] = None
    draft: Dict[str, Any] = Field(default_factory=dict)


class CompleteStepRequest(BaseModel):
    """Opaque step payload — validated per-step inside the service."""
    data: Dict[str, Any] = Field(default_factory=dict)


class SkipStepRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class GoLiveRequest(BaseModel):
    publish_branding: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


# ── Responses ────────────────────────────────────────────────────────────────

class ChecklistItem(BaseModel):
    step: str
    title: str
    optional: bool
    status: str
    estimated_minutes: int
    integration: str


class ProgressTracker(BaseModel):
    current_step: OnboardingStep
    current_order: int
    total_steps: int
    completed_count: int
    skipped_count: int
    percent_complete: float
    estimated_minutes_total: int
    estimated_minutes_remaining: int
    status: OnboardingStatus


class OnboardingSessionResponse(BaseModel):
    id: UUID
    resume_token: str
    user_id: UUID
    company_id: UUID
    status: OnboardingStatus
    current_step: OnboardingStep
    completed_steps: List[str] = Field(default_factory=list)
    skipped_steps: List[str] = Field(default_factory=list)
    draft_data: Dict[str, Any] = Field(default_factory=dict)
    resource_ids: Dict[str, Any] = Field(default_factory=dict)
    checklist: List[ChecklistItem] = Field(default_factory=list)
    progress: ProgressTracker
    started_at: datetime
    last_active_at: datetime
    paused_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StartOnboardingResponse(BaseModel):
    session: OnboardingSessionResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    next_actions: List[str] = Field(default_factory=list)


class StepDefinition(BaseModel):
    order: int
    step: str
    title: str
    description: str
    estimated_minutes: int
    integration: str
    optional: bool


class FlowDefinitionResponse(BaseModel):
    steps: List[StepDefinition]
    total_estimated_minutes: int
    optional_steps: List[str]
    integrations: List[str]


class StepActionResponse(BaseModel):
    session: OnboardingSessionResponse
    result: Dict[str, Any] = Field(default_factory=dict)
    next_step: Optional[OnboardingStep] = None


# ── Admin ────────────────────────────────────────────────────────────────────

class AdminSessionSummary(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID
    status: OnboardingStatus
    current_step: OnboardingStep
    completed_count: int
    skipped_count: int
    percent_complete: float
    started_at: datetime
    last_active_at: datetime
    completed_at: Optional[datetime] = None


class DropOffBucket(BaseModel):
    step: str
    title: str
    sessions_stuck: int
    entered_count: int
    completed_count: int
    skipped_count: int
    drop_off_rate: float


class OnboardingAnalyticsResponse(BaseModel):
    sessions_total: int
    in_progress: int
    paused: int
    completed: int
    abandoned: int
    completion_rate: float
    avg_completion_minutes: Optional[float] = None
    drop_off: List[DropOffBucket]
    funnel: List[Dict[str, Any]]


class AdminSessionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AdminSessionSummary]
