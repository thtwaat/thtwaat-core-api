"""add monitoring and admin operations

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

alert_severity = sa.Enum(
    "critical", "warning", "info",
    name="ops_alert_severity_enum",
)
alert_status = sa.Enum(
    "open", "acknowledged", "resolved",
    name="ops_alert_status_enum",
)
deployment_action = sa.Enum(
    "backup",
    "nginx_reload",
    "container_restart",
    "ssl_renew",
    "job_enqueue",
    "job_retry",
    "job_cancel",
    "publish",
    "other",
    name="ops_deployment_action_enum",
)


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    alert_severity.create(op.get_bind(), checkfirst=True)
    alert_status.create(op.get_bind(), checkfirst=True)
    deployment_action.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ops_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("severity", alert_severity, nullable=False, server_default="warning"),
        sa.Column("status", alert_status, nullable=False, server_default="open"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False, server_default="system"),
        sa.Column("metric", sa.String(100), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notified_channels", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_ops_alerts_fingerprint", "ops_alerts", ["fingerprint"])
    op.create_index("ix_ops_alerts_status_severity", "ops_alerts", ["status", "severity"])
    op.create_index("ix_ops_alerts_source", "ops_alerts", ["source"])

    op.create_table(
        "ops_deployment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("action", deployment_action, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="success"),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )
    op.create_index("ix_ops_deployment_events_action", "ops_deployment_events", ["action"])

    op.create_table(
        "ops_admin_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )
    op.create_index("ix_ops_admin_activities_category", "ops_admin_activities", ["category"])


def downgrade() -> None:
    op.drop_table("ops_admin_activities")
    op.drop_table("ops_deployment_events")
    op.drop_table("ops_alerts")
    deployment_action.drop(op.get_bind(), checkfirst=True)
    alert_status.drop(op.get_bind(), checkfirst=True)
    alert_severity.drop(op.get_bind(), checkfirst=True)
