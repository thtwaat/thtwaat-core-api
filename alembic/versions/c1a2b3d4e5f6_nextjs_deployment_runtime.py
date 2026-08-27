"""THTWAAT Deploy Phase 3 — Next.js runtime metadata.

Purely additive, all-nullable columns. Existing static_html/static_zip/vite
deployment rows are completely unaffected: runtime_type defaults to
"static" (matching their actual, unchanged serving mode), and
runtime_container_id/internal_port/health_status stay NULL for them forever.
company_domains.runtime_proxy_target mirrors the existing static_root_path
column (added in a692f4d3105b) for the new "nginx -> runtime container"
vhost mode (see app/ssl/nginx_gen.py RUNTIME_PROXY_LOCATION_BLOCK).

Revision ID: c1a2b3d4e5f6
Revises: aec4809e5929
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "aec4809e5929"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("static_site_deployments", "runtime_type"):
        op.add_column(
            "static_site_deployments",
            sa.Column("runtime_type", sa.String(length=16), nullable=True, server_default="static"),
        )
    if not _has_column("static_site_deployments", "runtime_container_id"):
        op.add_column(
            "static_site_deployments",
            sa.Column("runtime_container_id", sa.String(length=128), nullable=True),
        )
    if not _has_column("static_site_deployments", "internal_port"):
        op.add_column(
            "static_site_deployments",
            sa.Column("internal_port", sa.Integer(), nullable=True),
        )
    if not _has_column("static_site_deployments", "health_status"):
        op.add_column(
            "static_site_deployments",
            sa.Column("health_status", sa.String(length=16), nullable=True),
        )
    if not _has_column("company_domains", "runtime_proxy_target"):
        op.add_column(
            "company_domains",
            sa.Column("runtime_proxy_target", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    if _has_column("company_domains", "runtime_proxy_target"):
        op.drop_column("company_domains", "runtime_proxy_target")
    if _has_column("static_site_deployments", "health_status"):
        op.drop_column("static_site_deployments", "health_status")
    if _has_column("static_site_deployments", "internal_port"):
        op.drop_column("static_site_deployments", "internal_port")
    if _has_column("static_site_deployments", "runtime_container_id"):
        op.drop_column("static_site_deployments", "runtime_container_id")
    if _has_column("static_site_deployments", "runtime_type"):
        op.drop_column("static_site_deployments", "runtime_type")
