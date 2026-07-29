"""Onboarding wizard persistence models."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin
from app.onboarding.steps import OnboardingStatus, OnboardingStep, StepEventType


class OnboardingSession(Base, TimestampMixin):
    """One wizard run per owner user (resume-later via resume_token)."""

    __tablename__ = "onboarding_sessions"
    __table_args__ = (
        Index("ix_onboarding_sessions_company", "company_id"),
        Index("ix_onboarding_sessions_status", "status"),
        Index("ix_onboarding_sessions_current_step", "current_step"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_token = Column(String(64), unique=True, nullable=False, index=True)

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status = Column(
        SAEnum(
            OnboardingStatus,
            name="onboarding_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=OnboardingStatus.IN_PROGRESS,
    )
    current_step = Column(
        SAEnum(
            OnboardingStep,
            name="onboarding_step_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=OnboardingStep.VERIFY_EMAIL,
    )

    completed_steps = Column(JSONB, nullable=False, default=list)
    skipped_steps = Column(JSONB, nullable=False, default=list)
    draft_data = Column(JSONB, nullable=False, default=dict)
    resource_ids = Column(JSONB, nullable=False, default=dict)
    checklist = Column(JSONB, nullable=False, default=list)

    estimated_minutes_total = Column(Integer, nullable=False, default=43)
    estimated_minutes_remaining = Column(Integer, nullable=False, default=41)

    started_at = Column(DateTime(timezone=True), nullable=False)
    last_active_at = Column(DateTime(timezone=True), nullable=False)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    abandoned_at = Column(DateTime(timezone=True), nullable=True)

    last_error = Column(Text, nullable=True)


class OnboardingStepEvent(Base, TimestampMixin):
    """Analytics funnel events for drop-off and completion metrics."""

    __tablename__ = "onboarding_step_events"
    __table_args__ = (
        Index("ix_onboarding_step_events_session", "session_id"),
        Index("ix_onboarding_step_events_step_type", "step", "event_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    step = Column(
        SAEnum(
            OnboardingStep,
            name="onboarding_step_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    event_type = Column(
        SAEnum(
            StepEventType,
            name="onboarding_step_event_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    payload = Column(JSONB, nullable=False, default=dict)
    duration_ms = Column(Integer, nullable=True)
