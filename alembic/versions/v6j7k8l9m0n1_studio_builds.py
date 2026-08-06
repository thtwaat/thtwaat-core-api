"""Studio project builds table (AI Software Factory).

Revision ID: v6j7k8l9m0n1
Revises: u5i6j7k8l9m0
Create Date: 2026-08-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v6j7k8l9m0n1"
down_revision: Union[str, Sequence[str], None] = "u5i6j7k8l9m0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("studio_project_builds"):
        return

    op.create_table(
        "studio_project_builds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="queued"),
        sa.Column(
            "agent_statuses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "logs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "file_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retry_of", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["approval_id"], ["studio_project_approvals.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("project_id", "version", name="uq_studio_builds_project_version"),
    )
    op.create_index("ix_studio_project_builds_id", "studio_project_builds", ["id"])
    op.create_index("ix_studio_project_builds_project_id", "studio_project_builds", ["project_id"])
    op.create_index(
        "ix_studio_project_builds_workspace_id", "studio_project_builds", ["workspace_id"]
    )
    op.create_index(
        "ix_studio_project_builds_approval_id", "studio_project_builds", ["approval_id"]
    )
    op.create_index(
        "ix_studio_builds_project_current",
        "studio_project_builds",
        ["project_id", "is_current"],
    )
    op.create_index(
        "ix_studio_builds_project_status",
        "studio_project_builds",
        ["project_id", "status"],
    )


def downgrade() -> None:
    if not _has_table("studio_project_builds"):
        return
    op.drop_index("ix_studio_builds_project_status", table_name="studio_project_builds")
    op.drop_index("ix_studio_builds_project_current", table_name="studio_project_builds")
    op.drop_index("ix_studio_project_builds_approval_id", table_name="studio_project_builds")
    op.drop_index("ix_studio_project_builds_workspace_id", table_name="studio_project_builds")
    op.drop_index("ix_studio_project_builds_project_id", table_name="studio_project_builds")
    op.drop_index("ix_studio_project_builds_id", table_name="studio_project_builds")
    op.drop_table("studio_project_builds")
