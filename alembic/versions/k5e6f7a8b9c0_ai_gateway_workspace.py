"""Additive migration: AI Gateway workspace settings.

Revision ID: k5e6f7a8b9c0
Revises: j4d5e6f7a8b9
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "k5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "j4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_gateway_workspace_settings" in inspector.get_table_names():
        return
    op.create_table(
        "ai_gateway_workspace_settings",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("default_provider", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("allowed_providers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("monthly_token_limit", sa.Integer(), nullable=True),
        sa.Column("monthly_request_limit", sa.Integer(), nullable=True),
        sa.Column("monthly_cost_limit_usd", sa.Float(), nullable=True),
        sa.Column("routing_policy", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("retry_max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("timeout_seconds", sa.Float(), nullable=False, server_default="60"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("company_id"),
    )


def downgrade() -> None:
    pass
