"""Agent soft-delete and restore retention fields.

Revision ID: x8l9m0n1o2p3
Revises: w7k8l9m0n1o2
Create Date: 2026-08-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "x8l9m0n1o2p3"
down_revision: Union[str, Sequence[str], None] = "w7k8l9m0n1o2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("agent_configs", "deleted_at"):
        op.add_column(
            "agent_configs",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column("agent_configs", "deleted_by"):
        op.add_column(
            "agent_configs",
            sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if not _has_column("agent_configs", "delete_reason"):
        op.add_column(
            "agent_configs",
            sa.Column("delete_reason", sa.Text(), nullable=True),
        )
    if not _has_column("agent_configs", "delete_options"):
        op.add_column(
            "agent_configs",
            sa.Column(
                "delete_options",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    bind = op.get_bind()
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("agent_configs")}
    if "ix_agent_configs_deleted_at" not in indexes:
        op.create_index(
            "ix_agent_configs_deleted_at",
            "agent_configs",
            ["deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("agent_configs")}
    if "ix_agent_configs_deleted_at" in indexes:
        op.drop_index("ix_agent_configs_deleted_at", table_name="agent_configs")
    for col in ("delete_options", "delete_reason", "deleted_by", "deleted_at"):
        if _has_column("agent_configs", col):
            op.drop_column("agent_configs", col)
