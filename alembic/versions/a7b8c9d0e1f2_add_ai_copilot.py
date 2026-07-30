"""add ai copilot orchestration

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

message_role = postgresql.ENUM(
    "user", "assistant", "system", "tool",
    name="copilot_message_role_enum",
    create_type=False,
)
task_status = postgresql.ENUM(
    "planned",
    "awaiting_confirmation",
    "running",
    "completed",
    "failed",
    "cancelled",
    name="copilot_task_status_enum",
    create_type=False,
)
step_status = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "awaiting_confirmation",
    name="copilot_step_status_enum",
    create_type=False,
)


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    message_role.create(op.get_bind(), checkfirst=True)
    task_status.create(op.get_bind(), checkfirst=True)
    step_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "copilot_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("memory", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.String(16), nullable=False, server_default="active"),
        *_timestamps(),
    )
    op.create_index("ix_copilot_conversations_company_id", "copilot_conversations", ["company_id"])
    op.create_index("ix_copilot_conversations_user_id", "copilot_conversations", ["user_id"])
    op.create_index(
        "ix_copilot_conversations_company_user",
        "copilot_conversations",
        ["company_id", "user_id"],
    )

    op.create_table(
        "copilot_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )
    op.create_index(
        "ix_copilot_messages_conversation",
        "copilot_messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "copilot_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intent", sa.String(64), nullable=False),
        sa.Column("status", task_status, nullable=False, server_default="planned"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("slots", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requires_confirmation", sa.String(8), nullable=False, server_default="false"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "parent_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copilot_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
    )
    op.create_index("ix_copilot_tasks_company_status", "copilot_tasks", ["company_id", "status"])
    op.create_index("ix_copilot_tasks_conversation", "copilot_tasks", ["conversation_id"])

    op.create_table(
        "copilot_task_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copilot_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", step_status, nullable=False, server_default="pending"),
        sa.Column("input_args", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_copilot_task_steps_task", "copilot_task_steps", ["task_id", "step_index"])


def downgrade() -> None:
    op.drop_table("copilot_task_steps")
    op.drop_table("copilot_tasks")
    op.drop_table("copilot_messages")
    op.drop_table("copilot_conversations")
    step_status.drop(op.get_bind(), checkfirst=True)
    task_status.drop(op.get_bind(), checkfirst=True)
    message_role.drop(op.get_bind(), checkfirst=True)
