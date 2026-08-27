"""THTWAAT Deploy Phase 5C — Git Push -> Auto Deploy.

Purely additive: (1) source_provider/github_* columns on
static_site_deployments so a webhook-triggered deployment records exactly
which repository/branch/commit it was built from (source_provider defaults
to "upload" so every existing row is unaffected), and (2)
github_webhook_deliveries, a minimal idempotency-claim table keyed on
GitHub's X-GitHub-Delivery header so a retried webhook delivery can never
trigger a second deployment. No existing table/column is altered or
dropped, and no webhook secret or credential is ever stored here.

Revision ID: 435fcac3713f
Revises: f4a5b6c7d8e9
Create Date: 2026-08-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "435fcac3713f"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("static_site_deployments", "source_provider"):
        op.add_column(
            "static_site_deployments",
            sa.Column("source_provider", sa.String(length=16), nullable=False, server_default="upload"),
        )
        op.alter_column("static_site_deployments", "source_provider", server_default=None)
    if not _has_column("static_site_deployments", "github_repository_owner"):
        op.add_column(
            "static_site_deployments",
            sa.Column("github_repository_owner", sa.String(length=255), nullable=True),
        )
    if not _has_column("static_site_deployments", "github_repository_name"):
        op.add_column(
            "static_site_deployments",
            sa.Column("github_repository_name", sa.String(length=255), nullable=True),
        )
    if not _has_column("static_site_deployments", "github_commit_sha"):
        op.add_column(
            "static_site_deployments",
            sa.Column("github_commit_sha", sa.String(length=64), nullable=True),
        )
    if not _has_column("static_site_deployments", "github_branch"):
        op.add_column(
            "static_site_deployments",
            sa.Column("github_branch", sa.String(length=255), nullable=True),
        )

    if not _has_table("github_webhook_deliveries"):
        op.create_table(
            "github_webhook_deliveries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("delivery_id", sa.String(length=128), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("repository_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="received"),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("delivery_id", name="uq_github_webhook_deliveries_delivery_id"),
        )
        op.create_index(
            "ix_github_webhook_deliveries_delivery_id", "github_webhook_deliveries", ["delivery_id"]
        )
        op.create_index(
            "ix_github_webhook_deliveries_repository", "github_webhook_deliveries", ["repository_id"]
        )


def downgrade() -> None:
    if _has_table("github_webhook_deliveries"):
        op.drop_index("ix_github_webhook_deliveries_repository", table_name="github_webhook_deliveries")
        op.drop_index("ix_github_webhook_deliveries_delivery_id", table_name="github_webhook_deliveries")
        op.drop_table("github_webhook_deliveries")

    for column in (
        "github_branch",
        "github_commit_sha",
        "github_repository_name",
        "github_repository_owner",
        "source_provider",
    ):
        if _has_column("static_site_deployments", column):
            op.drop_column("static_site_deployments", column)
