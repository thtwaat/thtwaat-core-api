"""add customer onboarding wizard

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

onboarding_status = sa.Enum(
    "in_progress", "paused", "completed", "abandoned",
    name="onboarding_status_enum",
)
onboarding_step = sa.Enum(
    "create_account",
    "verify_email",
    "create_company",
    "choose_plan",
    "create_ai_agent",
    "upload_knowledge",
    "choose_template",
    "generate_product",
    "preview",
    "publish",
    "connect_domain",
    "go_live",
    name="onboarding_step_enum",
)
onboarding_event_type = sa.Enum(
    "entered", "autosaved", "completed", "skipped", "failed", "paused", "resumed",
    name="onboarding_step_event_type_enum",
)


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    onboarding_status.create(op.get_bind(), checkfirst=True)
    onboarding_step.create(op.get_bind(), checkfirst=True)
    onboarding_event_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "onboarding_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("resume_token", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", onboarding_status, nullable=False, server_default="in_progress"),
        sa.Column("current_step", onboarding_step, nullable=False, server_default="verify_email"),
        sa.Column("completed_steps", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skipped_steps", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("draft_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resource_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("checklist", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("estimated_minutes_total", sa.Integer(), nullable=False, server_default="43"),
        sa.Column("estimated_minutes_remaining", sa.Integer(), nullable=False, server_default="41"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_onboarding_sessions_resume_token", "onboarding_sessions", ["resume_token"], unique=True)
    op.create_index("ix_onboarding_sessions_user_id", "onboarding_sessions", ["user_id"])
    op.create_index("ix_onboarding_sessions_company", "onboarding_sessions", ["company_id"])
    op.create_index("ix_onboarding_sessions_status", "onboarding_sessions", ["status"])
    op.create_index("ix_onboarding_sessions_current_step", "onboarding_sessions", ["current_step"])

    op.create_table(
        "onboarding_step_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("onboarding_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("step", onboarding_step, nullable=False),
        sa.Column("event_type", onboarding_event_type, nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_onboarding_step_events_session", "onboarding_step_events", ["session_id"])
    op.create_index(
        "ix_onboarding_step_events_step_type",
        "onboarding_step_events",
        ["step", "event_type"],
    )


def downgrade() -> None:
    op.drop_table("onboarding_step_events")
    op.drop_table("onboarding_sessions")
    onboarding_event_type.drop(op.get_bind(), checkfirst=True)
    onboarding_step.drop(op.get_bind(), checkfirst=True)
    onboarding_status.drop(op.get_bind(), checkfirst=True)
