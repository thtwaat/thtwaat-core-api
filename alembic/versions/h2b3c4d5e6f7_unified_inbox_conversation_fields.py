"""Add Unified Inbox fields on agent_conversations (channel, status, assign, read).

Revision ID: h2b3c4d5e6f7
Revises: g1a2b3c4d5e6
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "g1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "agent_conversations"


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return index_name in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _has_table(TABLE):
        return

    if not _has_column(TABLE, "channel"):
        op.add_column(
            TABLE,
            sa.Column("channel", sa.String(length=32), nullable=False, server_default="dashboard"),
        )
    if not _has_column(TABLE, "status"):
        op.add_column(
            TABLE,
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        )
    if not _has_column(TABLE, "assigned_to_user_id"):
        op.add_column(
            TABLE,
            sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_agent_conversations_assigned_to_user_id",
            TABLE,
            "users",
            ["assigned_to_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _has_column(TABLE, "last_read_at"):
        op.add_column(
            TABLE,
            sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column(TABLE, "extra_metadata"):
        op.add_column(
            TABLE,
            sa.Column(
                "extra_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    for name, cols in (
        ("ix_agent_conversations_channel", ["channel"]),
        ("ix_agent_conversations_status", ["status"]),
        ("ix_agent_conversations_assigned_to", ["assigned_to_user_id"]),
    ):
        if not _has_index(TABLE, name):
            op.create_index(name, TABLE, cols, unique=False)


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    for name in (
        "ix_agent_conversations_assigned_to",
        "ix_agent_conversations_status",
        "ix_agent_conversations_channel",
    ):
        if _has_index(TABLE, name):
            op.drop_index(name, table_name=TABLE)
    if _has_column(TABLE, "assigned_to_user_id"):
        op.drop_constraint(
            "fk_agent_conversations_assigned_to_user_id", TABLE, type_="foreignkey"
        )
        op.drop_column(TABLE, "assigned_to_user_id")
    for col in ("extra_metadata", "last_read_at", "status", "channel"):
        if _has_column(TABLE, col):
            op.drop_column(TABLE, col)
