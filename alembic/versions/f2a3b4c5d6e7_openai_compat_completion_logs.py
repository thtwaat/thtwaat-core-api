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

TABLE = "openai_completion_logs"


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return index_name in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _has_table(TABLE):
        op.create_table(
            TABLE,
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
            sa.Column(
                "request_messages",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
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

    indexes = (
        ("ix_openai_completion_logs_company_id", ["company_id"], False),
        ("ix_openai_completion_logs_api_key_id", ["api_key_id"], False),
        ("ix_openai_completion_logs_agent_id", ["agent_id"], False),
        ("ix_openai_completion_logs_completion_id", ["completion_id"], True),
    )
    for name, cols, unique in indexes:
        if not _has_index(TABLE, name):
            op.create_index(name, TABLE, cols, unique=unique)


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    for name in (
        "ix_openai_completion_logs_completion_id",
        "ix_openai_completion_logs_agent_id",
        "ix_openai_completion_logs_api_key_id",
        "ix_openai_completion_logs_company_id",
    ):
        if _has_index(TABLE, name):
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
