"""Studio project infrastructure manifests table.

Revision ID: t4h5i6j7k8l9
Revises: s3g4h5i6j7k8
Create Date: 2026-08-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t4h5i6j7k8l9"
down_revision: Union[str, Sequence[str], None] = "s3g4h5i6j7k8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("studio_project_infrastructures"):
        return

    op.create_table(
        "studio_project_infrastructures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("build_plan_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("frontend_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("backend_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ai_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column(
            "manifest",
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
        sa.UniqueConstraint("project_id", "version", name="uq_studio_infra_project_version"),
    )
    op.create_index(
        "ix_studio_project_infrastructures_id", "studio_project_infrastructures", ["id"]
    )
    op.create_index(
        "ix_studio_project_infrastructures_project_id",
        "studio_project_infrastructures",
        ["project_id"],
    )
    op.create_index(
        "ix_studio_project_infrastructures_workspace_id",
        "studio_project_infrastructures",
        ["workspace_id"],
    )
    op.create_index(
        "ix_studio_infra_project_current",
        "studio_project_infrastructures",
        ["project_id", "is_current"],
    )


def downgrade() -> None:
    if not _has_table("studio_project_infrastructures"):
        return
    op.drop_index("ix_studio_infra_project_current", table_name="studio_project_infrastructures")
    op.drop_index(
        "ix_studio_project_infrastructures_workspace_id",
        table_name="studio_project_infrastructures",
    )
    op.drop_index(
        "ix_studio_project_infrastructures_project_id",
        table_name="studio_project_infrastructures",
    )
    op.drop_index("ix_studio_project_infrastructures_id", table_name="studio_project_infrastructures")
    op.drop_table("studio_project_infrastructures")
