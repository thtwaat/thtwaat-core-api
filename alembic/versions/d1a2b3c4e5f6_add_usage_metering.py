"""Add usage metering tables and plan limit columns.

Revision ID: d1a2b3c4e5f6
Revises: c4e9f1a2b8d0
Create Date: 2026-07-29 10:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d1a2b3c4e5f6"
down_revision: Union[str, Sequence[str], None] = "c4e9f1a2b8d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_table("usage_events"):
        op.create_table(
            "usage_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("dimension", sa.String(length=64), nullable=False),
            sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="1"),
            sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("widget_id", sa.String(length=64), nullable=True),
            sa.Column("source", sa.String(length=64), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_usage_events_id", "usage_events", ["id"])
        op.create_index("ix_usage_events_company_id", "usage_events", ["company_id"])
        op.create_index("ix_usage_events_dimension", "usage_events", ["dimension"])
        op.create_index("ix_usage_events_agent_id", "usage_events", ["agent_id"])
        op.create_index("ix_usage_events_api_key_id", "usage_events", ["api_key_id"])
        op.create_index("ix_usage_events_widget_id", "usage_events", ["widget_id"])

    if not _has_table("company_usage_meters"):
        op.create_table(
            "company_usage_meters",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("period_type", sa.String(length=16), nullable=False, server_default="monthly"),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("plan_key", sa.String(length=50), nullable=False, server_default="free"),
            sa.Column("ai_messages", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("conversations", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("prompt_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("api_requests", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("widget_requests", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("knowledge_searches", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("knowledge_upload_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("storage_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("agents_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("active_users", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("api_keys", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("domains", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("templates_published", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_agents", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_messages", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("max_tokens", sa.BigInteger(), nullable=False, server_default="50000"),
            sa.Column("max_storage", sa.BigInteger(), nullable=False, server_default="104857600"),
            sa.Column("max_domains", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_team_members", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("max_api_keys", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_templates", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("company_id", "period_start", "period_type", name="uq_usage_meter_period"),
        )
        op.create_index("ix_company_usage_meters_id", "company_usage_meters", ["id"])
        op.create_index("ix_usage_meter_company_period", "company_usage_meters", ["company_id", "period_type"])

    if not _has_table("usage_daily_aggregates"):
        op.create_table(
            "usage_daily_aggregates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("day", sa.DateTime(timezone=True), nullable=False),
            sa.Column("dimension", sa.String(length=64), nullable=False),
            sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("company_id", "day", "dimension", name="uq_usage_daily_dim"),
        )
        op.create_index("ix_usage_daily_aggregates_id", "usage_daily_aggregates", ["id"])
        op.create_index("ix_usage_daily_aggregates_company_id", "usage_daily_aggregates", ["company_id"])
        op.create_index("ix_usage_daily_aggregates_day", "usage_daily_aggregates", ["day"])

    # Extend plans with usage limit columns when table already exists (non-breaking)
    plan_cols = [
        ("max_agents", sa.Integer(), "1"),
        ("max_messages", sa.Integer(), "100"),
        ("max_tokens", sa.BigInteger(), "50000"),
        ("max_storage", sa.BigInteger(), "104857600"),
        ("max_domains", sa.Integer(), "0"),
        ("max_team_members", sa.Integer(), "5"),
        ("max_api_keys", sa.Integer(), "1"),
        ("max_templates", sa.Integer(), "0"),
    ]
    if _has_table("plans"):
        for name, col_type, default in plan_cols:
            if not _has_column("plans", name):
                op.add_column(
                    "plans",
                    sa.Column(name, col_type, nullable=False, server_default=default),
                )


def downgrade() -> None:
    if _has_table("plans"):
        for name in (
            "max_templates",
            "max_api_keys",
            "max_team_members",
            "max_domains",
            "max_storage",
            "max_tokens",
            "max_messages",
            "max_agents",
        ):
            if _has_column("plans", name):
                op.drop_column("plans", name)

    if _has_table("usage_daily_aggregates"):
        op.drop_table("usage_daily_aggregates")
    if _has_table("company_usage_meters"):
        op.drop_table("company_usage_meters")
    if _has_table("usage_events"):
        op.drop_table("usage_events")
