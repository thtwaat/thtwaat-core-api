"""Add openai_completion_logs for OpenAI-compatible /v1/chat/completions audit.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "openai_completion_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completion_id", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="stub"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finish_reason", sa.String(length=32), nullable=True),
        sa.Column("request_messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_content", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="succeeded"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_openai_completion_logs_company_id",
        "openai_completion_logs",
        ["company_id"],
    )
    op.create_index(
        "ix_openai_completion_logs_api_key_id",
        "openai_completion_logs",
        ["api_key_id"],
    )
    op.create_index(
        "ix_openai_completion_logs_agent_id",
        "openai_completion_logs",
        ["agent_id"],
    )
    op.create_index(
        "ix_openai_completion_logs_completion_id",
        "openai_completion_logs",
        ["completion_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_openai_completion_logs_completion_id", table_name="openai_completion_logs")
    op.drop_index("ix_openai_completion_logs_agent_id", table_name="openai_completion_logs")
    op.drop_index("ix_openai_completion_logs_api_key_id", table_name="openai_completion_logs")
    op.drop_index("ix_openai_completion_logs_company_id", table_name="openai_completion_logs")
    op.drop_table("openai_completion_logs")
