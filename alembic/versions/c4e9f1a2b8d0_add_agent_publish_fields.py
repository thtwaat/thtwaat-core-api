"""Add publish fields to agents and extend agent_api_keys.

Revision ID: c4e9f1a2b8d0
Revises: abf83f36755c
Create Date: 2026-07-29 09:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e9f1a2b8d0"
down_revision: Union[str, Sequence[str], None] = "abf83f36755c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_configs", sa.Column("widget_id", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_agent_configs_widget_id"), "agent_configs", ["widget_id"], unique=True)

    op.add_column("agent_api_keys", sa.Column("key_prefix", sa.String(length=32), nullable=True))
    op.add_column("agent_api_keys", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_api_keys", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_api_keys", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_agent_api_keys_key_prefix"), "agent_api_keys", ["key_prefix"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_api_keys_key_prefix"), table_name="agent_api_keys")
    op.drop_column("agent_api_keys", "revoked_at")
    op.drop_column("agent_api_keys", "expires_at")
    op.drop_column("agent_api_keys", "last_used_at")
    op.drop_column("agent_api_keys", "key_prefix")

    op.drop_index(op.f("ix_agent_configs_widget_id"), table_name="agent_configs")
    op.drop_column("agent_configs", "widget_id")
    op.drop_column("agent_configs", "published_at")
