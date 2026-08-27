"""THTWAAT Deploy Phase 4B — static_site_deployment_env_vars snapshot table.

Adds the immutable, per-deployment environment-variable snapshot (see
app/static_sites/models.py::StaticSiteDeploymentEnvVar and
app/static_sites/env_resolver.py). Purely additive — no existing table or
column is touched.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-21
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("static_site_deployment_env_vars"):
        return
    op.create_table(
        "static_site_deployment_env_vars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "deployment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("static_site_deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "deployment_id", "key", name="uq_static_site_deployment_env_vars_deployment_key"
        ),
    )
    op.create_index(
        "ix_static_site_deployment_env_vars_deployment",
        "static_site_deployment_env_vars",
        ["deployment_id"],
    )


def downgrade() -> None:
    if not _has_table("static_site_deployment_env_vars"):
        return
    op.drop_index(
        "ix_static_site_deployment_env_vars_deployment", table_name="static_site_deployment_env_vars"
    )
    op.drop_table("static_site_deployment_env_vars")
