"""THTWAAT Deploy — static_sites, static_site_deployments, domain static_root_path.

Adds:
  - static_sites: minimal sibling project entity for uploaded HTML/ZIP sites
    (kept separate from studio_projects because StudioProject.prompt is
    NOT NULL and AI-pipeline specific — see app/static_sites/models.py).
  - static_site_deployments: mirrors StudioProjectDeployment's versioning/
    rollback/audit column conventions, kept as a sibling table rather than a
    reuse because studio_project_deployments.project_id is a NOT NULL CASCADE
    FK into studio_projects — reusing it would require weakening a
    constraint the existing AI-generated Studio deploy flow relies on.
  - company_domains.static_root_path: nullable column, NULL for every
    existing domain. Only THTWAAT Deploy sets it; app/ssl/nginx_gen.py and
    app/ssl/manager.py treat it as fully optional (proxy-mode unchanged).

Revision ID: a692f4d3105b
Revises: z0n1o2p3q4r5
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a692f4d3105b"
down_revision: Union[str, Sequence[str], None] = "z0n1o2p3q4r5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("company_domains", "static_root_path"):
        op.add_column(
            "company_domains",
            sa.Column("static_root_path", sa.Text(), nullable=True),
        )

    if not _has_table("static_sites"):
        op.create_table(
            "static_sites",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
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
            sa.ForeignKeyConstraint(["workspace_id"], ["companies.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("workspace_id", "slug", name="uq_static_sites_workspace_slug"),
        )
        op.create_index("ix_static_sites_id", "static_sites", ["id"])
        op.create_index("ix_static_sites_workspace_id", "static_sites", ["workspace_id"])
        op.create_index("ix_static_sites_user_id", "static_sites", ["user_id"])
        op.create_index("ix_static_sites_workspace", "static_sites", ["workspace_id"])

    if not _has_table("static_site_deployments"):
        op.create_table(
            "static_site_deployments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("provider", sa.String(length=64), nullable=False, server_default="static"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("stage", sa.String(length=64), nullable=False, server_default="queued"),
            sa.Column("source_type", sa.String(length=16), nullable=False, server_default="zip"),
            sa.Column("upload_filename", sa.String(length=255), nullable=True),
            sa.Column("upload_size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("deployment_path", sa.Text(), nullable=True),
            sa.Column("domain", sa.String(length=255), nullable=True),
            sa.Column("subdomain", sa.String(length=255), nullable=True),
            sa.Column("environment", sa.String(length=32), nullable=False, server_default="production"),
            sa.Column("live", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "health", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "ssl", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "instructions", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "logs", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("rollback_of", postgresql.UUID(as_uuid=True), nullable=True),
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
            sa.ForeignKeyConstraint(["site_id"], ["static_sites.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workspace_id"], ["companies.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("site_id", "version", name="uq_static_site_deploys_site_version"),
        )
        op.create_index("ix_static_site_deployments_id", "static_site_deployments", ["id"])
        op.create_index("ix_static_site_deployments_site_id", "static_site_deployments", ["site_id"])
        op.create_index("ix_static_site_deployments_workspace_id", "static_site_deployments", ["workspace_id"])
        op.create_index(
            "ix_static_site_deploys_site_current", "static_site_deployments", ["site_id", "is_current"]
        )
        op.create_index(
            "ix_static_site_deploys_site_status", "static_site_deployments", ["site_id", "status"]
        )


def downgrade() -> None:
    if _has_table("static_site_deployments"):
        op.drop_index("ix_static_site_deploys_site_status", table_name="static_site_deployments")
        op.drop_index("ix_static_site_deploys_site_current", table_name="static_site_deployments")
        op.drop_index("ix_static_site_deployments_workspace_id", table_name="static_site_deployments")
        op.drop_index("ix_static_site_deployments_site_id", table_name="static_site_deployments")
        op.drop_index("ix_static_site_deployments_id", table_name="static_site_deployments")
        op.drop_table("static_site_deployments")

    if _has_table("static_sites"):
        op.drop_index("ix_static_sites_workspace", table_name="static_sites")
        op.drop_index("ix_static_sites_user_id", table_name="static_sites")
        op.drop_index("ix_static_sites_workspace_id", table_name="static_sites")
        op.drop_index("ix_static_sites_id", table_name="static_sites")
        op.drop_table("static_sites")

    if _has_column("company_domains", "static_root_path"):
        op.drop_column("company_domains", "static_root_path")
