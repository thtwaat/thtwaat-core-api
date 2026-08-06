"""Studio project build plans table.

Revision ID: p0d1e2f3a4b5
Revises: o9c0d1e2f3a4
Create Date: 2026-08-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "o9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("studio_project_build_plans"):
        return

    op.create_table(
        "studio_project_build_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "modules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "dependency_graph",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "dependency_tree",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "build_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["studio_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version", name="uq_studio_build_plan_project_version"),
    )
    op.create_index("ix_studio_project_build_plans_id", "studio_project_build_plans", ["id"])
    op.create_index(
        "ix_studio_project_build_plans_project_id",
        "studio_project_build_plans",
        ["project_id"],
    )
    op.create_index(
        "ix_studio_project_build_plans_workspace_id",
        "studio_project_build_plans",
        ["workspace_id"],
    )
    op.create_index(
        "ix_studio_build_plans_project_current",
        "studio_project_build_plans",
        ["project_id", "is_current"],
    )


def downgrade() -> None:
    if not _has_table("studio_project_build_plans"):
        return
    op.drop_index("ix_studio_build_plans_project_current", table_name="studio_project_build_plans")
    op.drop_index(
        "ix_studio_project_build_plans_workspace_id",
        table_name="studio_project_build_plans",
    )
    op.drop_index(
        "ix_studio_project_build_plans_project_id",
        table_name="studio_project_build_plans",
    )
    op.drop_index("ix_studio_project_build_plans_id", table_name="studio_project_build_plans")
    op.drop_table("studio_project_build_plans")
