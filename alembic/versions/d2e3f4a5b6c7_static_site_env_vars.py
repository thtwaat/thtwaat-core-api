"""THTWAAT Deploy Phase 4A — static_site_env_vars table.

Adds the encrypted-at-rest environment-variable store for static-site
deployments (see app/static_sites/models.py::StaticSiteEnvironmentVariable
and app/static_sites/env_crypto.py). Purely additive — no existing table or
column is touched, and no build/runtime injection is wired up yet (Phase 4B).

``environment`` is a plain varchar (not a DB enum) so a later phase can add
"preview" as an allowed value via an application-level change only.

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-08-21
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("static_site_env_vars"):
        return
    op.create_table(
        "static_site_env_vars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("static_sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="production"),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "site_id", "environment", "key", name="uq_static_site_env_vars_site_env_key"
        ),
    )
    op.create_index(
        "ix_static_site_env_vars_workspace", "static_site_env_vars", ["workspace_id"]
    )
    op.create_index("ix_static_site_env_vars_site", "static_site_env_vars", ["site_id"])
    op.create_index(
        "ix_static_site_env_vars_site_environment",
        "static_site_env_vars",
        ["site_id", "environment"],
    )


def downgrade() -> None:
    if not _has_table("static_site_env_vars"):
        return
    op.drop_index("ix_static_site_env_vars_site_environment", table_name="static_site_env_vars")
    op.drop_index("ix_static_site_env_vars_site", table_name="static_site_env_vars")
    op.drop_index("ix_static_site_env_vars_workspace", table_name="static_site_env_vars")
    op.drop_table("static_site_env_vars")
