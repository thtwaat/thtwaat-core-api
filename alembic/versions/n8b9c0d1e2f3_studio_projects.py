"""Studio projects table for THTWAAT Studio Phase 1.

Revision ID: n8b9c0d1e2f3
Revises: m7a8b9c0d1e2
Create Date: 2026-08-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "m7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_NAME = "studio_project_status_enum"
_ENUM_VALUES = (
    "draft",
    "analyzing",
    "blueprint_ready",
    "approved",
    "building",
    "completed",
    "failed",
)


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_type(name: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :n LIMIT 1"),
        {"n": name},
    ).scalar()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()

    # Enum may already exist from a partial failed run — never re-CREATE blindly.
    if not _has_type(_ENUM_NAME):
        bind.execute(
            sa.text(
                f"""
                DO $$ BEGIN
                    CREATE TYPE {_ENUM_NAME} AS ENUM (
                        'draft', 'analyzing', 'blueprint_ready', 'approved',
                        'building', 'completed', 'failed'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    if _has_table("studio_projects"):
        return

    status_enum = postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False)

    op.create_table(
        "studio_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default=sa.text("'draft'::studio_project_status_enum"),
        ),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_studio_projects_id", "studio_projects", ["id"])
    op.create_index("ix_studio_projects_workspace_id", "studio_projects", ["workspace_id"])
    op.create_index("ix_studio_projects_user_id", "studio_projects", ["user_id"])
    op.create_index("ix_studio_projects_status", "studio_projects", ["status"])
    op.create_index(
        "ix_studio_projects_workspace_status",
        "studio_projects",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_studio_projects_workspace_created",
        "studio_projects",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    if _has_table("studio_projects"):
        op.drop_index("ix_studio_projects_workspace_created", table_name="studio_projects")
        op.drop_index("ix_studio_projects_workspace_status", table_name="studio_projects")
        op.drop_index("ix_studio_projects_status", table_name="studio_projects")
        op.drop_index("ix_studio_projects_user_id", table_name="studio_projects")
        op.drop_index("ix_studio_projects_workspace_id", table_name="studio_projects")
        op.drop_index("ix_studio_projects_id", table_name="studio_projects")
        op.drop_table("studio_projects")
    if _has_type(_ENUM_NAME):
        op.execute(sa.text(f"DROP TYPE IF EXISTS {_ENUM_NAME}"))
