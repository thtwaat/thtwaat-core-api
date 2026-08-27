"""THTWAAT Deploy Phase 6A — Preview Deployments.

Purely additive: (1) static_site_preview_deployments + its env-var-snapshot
sibling table, structurally separate from static_site_deployments/
static_site_deployment_env_vars so ephemeral PR preview rows can never enter
the production rollback-candidate pool, and (2) three new plan-limit
columns (company_usage_meters.preview_deployments/max_preview_deployments,
plans.max_preview_deployments) extending the EXISTING usage-metering system
(app/usage/) — no new billing table, no existing column/price touched.

Revision ID: 27603ebdcff8
Revises: 435fcac3713f
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "27603ebdcff8"
down_revision: Union[str, Sequence[str], None] = "435fcac3713f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_table("static_site_preview_deployments"):
        op.create_table(
            "static_site_preview_deployments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "site_id", postgresql.UUID(as_uuid=True),
                sa.ForeignKey("static_sites.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column(
                "workspace_id", postgresql.UUID(as_uuid=True),
                sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("pr_number", sa.Integer(), nullable=False),
            sa.Column("branch", sa.String(length=255), nullable=False),
            sa.Column("base_branch", sa.String(length=255), nullable=True),
            sa.Column("github_repository_owner", sa.String(length=255), nullable=True),
            sa.Column("github_repository_name", sa.String(length=255), nullable=True),
            sa.Column("commit_sha", sa.String(length=64), nullable=False),
            sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
            sa.Column("stage", sa.String(length=64), nullable=False, server_default="queued"),
            sa.Column("hostname", sa.String(length=255), nullable=True),
            sa.Column("deployment_path", sa.Text(), nullable=True),
            sa.Column("framework", sa.String(length=32), nullable=True),
            sa.Column("runtime_type", sa.String(length=16), nullable=True, server_default="static"),
            sa.Column("runtime_container_id", sa.String(length=128), nullable=True),
            sa.Column("internal_port", sa.Integer(), nullable=True),
            sa.Column("health_status", sa.String(length=16), nullable=True),
            sa.Column("urls", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("logs", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("torn_down_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("teardown_reason", sa.String(length=32), nullable=True),
            sa.Column("source_provider", sa.String(length=16), nullable=False, server_default="github"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False,
            ),
            sa.UniqueConstraint("site_id", "pr_number", name="uq_static_site_previews_site_pr"),
        )
        op.create_index("ix_static_site_previews_site", "static_site_preview_deployments", ["site_id"])
        op.create_index(
            "ix_static_site_previews_expires_at", "static_site_preview_deployments", ["expires_at"]
        )

    if not _has_table("static_site_preview_deployment_env_vars"):
        op.create_table(
            "static_site_preview_deployment_env_vars",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "preview_deployment_id", postgresql.UUID(as_uuid=True),
                sa.ForeignKey("static_site_preview_deployments.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("encrypted_value", sa.Text(), nullable=False),
            sa.Column("environment", sa.String(length=32), nullable=False),
            sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False,
            ),
            sa.UniqueConstraint(
                "preview_deployment_id", "key", name="uq_static_site_preview_env_vars_preview_key"
            ),
        )
        op.create_index(
            "ix_static_site_preview_env_vars_preview",
            "static_site_preview_deployment_env_vars",
            ["preview_deployment_id"],
        )

    # ---- billing/usage extension (app/usage/) — no new table, no existing
    # column touched, no price changed. ------------------------------------
    if not _has_column("company_usage_meters", "preview_deployments"):
        op.add_column(
            "company_usage_meters",
            sa.Column("preview_deployments", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("company_usage_meters", "preview_deployments", server_default=None)
    if not _has_column("company_usage_meters", "max_preview_deployments"):
        op.add_column(
            "company_usage_meters",
            sa.Column("max_preview_deployments", sa.Integer(), nullable=False, server_default="1"),
        )
        op.alter_column("company_usage_meters", "max_preview_deployments", server_default=None)

    if not _has_column("plans", "max_preview_deployments"):
        op.add_column(
            "plans",
            sa.Column("max_preview_deployments", sa.Integer(), nullable=False, server_default="1"),
        )
        op.alter_column("plans", "max_preview_deployments", server_default=None)


def downgrade() -> None:
    if _has_column("plans", "max_preview_deployments"):
        op.drop_column("plans", "max_preview_deployments")
    if _has_column("company_usage_meters", "max_preview_deployments"):
        op.drop_column("company_usage_meters", "max_preview_deployments")
    if _has_column("company_usage_meters", "preview_deployments"):
        op.drop_column("company_usage_meters", "preview_deployments")

    if _has_table("static_site_preview_deployment_env_vars"):
        op.drop_index(
            "ix_static_site_preview_env_vars_preview", table_name="static_site_preview_deployment_env_vars"
        )
        op.drop_table("static_site_preview_deployment_env_vars")

    if _has_table("static_site_preview_deployments"):
        op.drop_index("ix_static_site_previews_expires_at", table_name="static_site_preview_deployments")
        op.drop_index("ix_static_site_previews_site", table_name="static_site_preview_deployments")
        op.drop_table("static_site_preview_deployments")
