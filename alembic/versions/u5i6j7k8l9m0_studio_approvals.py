"""Studio project approvals audit table.

Revision ID: u5i6j7k8l9m0
Revises: t4h5i6j7k8l9
Create Date: 2026-08-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u5i6j7k8l9m0"
down_revision: Union[str, Sequence[str], None] = "t4h5i6j7k8l9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("studio_project_approvals"):
        return

    op.create_table(
        "studio_project_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("build_plan_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("frontend_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backend_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "infrastructure_version", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "snapshot",
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
    )
    op.create_index("ix_studio_project_approvals_id", "studio_project_approvals", ["id"])
    op.create_index(
        "ix_studio_project_approvals_project_id", "studio_project_approvals", ["project_id"]
    )
    op.create_index(
        "ix_studio_project_approvals_workspace_id",
        "studio_project_approvals",
        ["workspace_id"],
    )
    op.create_index(
        "ix_studio_approvals_project_created",
        "studio_project_approvals",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    if not _has_table("studio_project_approvals"):
        return
    op.drop_index("ix_studio_approvals_project_created", table_name="studio_project_approvals")
    op.drop_index(
        "ix_studio_project_approvals_workspace_id", table_name="studio_project_approvals"
    )
    op.drop_index(
        "ix_studio_project_approvals_project_id", table_name="studio_project_approvals"
    )
    op.drop_index("ix_studio_project_approvals_id", table_name="studio_project_approvals")
    op.drop_table("studio_project_approvals")
