"""Add webhook_deliveries outbox for durable webhook.dispatch (Sem02 W4 Day 1).

Revision ID: g1a2b3c4d5e6
Revises: f2a3b4c5d6e7
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "webhook_deliveries"


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
            sa.Column("delivery_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("webhook_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("event", sa.String(length=128), nullable=False),
            sa.Column("url", sa.String(length=2048), nullable=False),
            sa.Column(
                "payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
            sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="SET NULL"),
        )

    indexes = (
        ("ix_webhook_deliveries_delivery_id", ["delivery_id"], True),
        ("ix_webhook_deliveries_company_id", ["company_id"], False),
        ("ix_webhook_deliveries_webhook_id", ["webhook_id"], False),
        ("ix_webhook_deliveries_event", ["event"], False),
        ("ix_webhook_deliveries_status", ["status"], False),
    )
    for name, cols, unique in indexes:
        if not _has_index(TABLE, name):
            op.create_index(name, TABLE, cols, unique=unique)


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    for name in (
        "ix_webhook_deliveries_status",
        "ix_webhook_deliveries_event",
        "ix_webhook_deliveries_webhook_id",
        "ix_webhook_deliveries_company_id",
        "ix_webhook_deliveries_delivery_id",
    ):
        if _has_index(TABLE, name):
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
