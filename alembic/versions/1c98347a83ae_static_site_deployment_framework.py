"""THTWAAT Deploy Phase 2 — static_site_deployments.framework (Vite detection).

Adds one nullable column recording the detected project framework
(static_html | static_zip | vite) per deployment version — see
app/static_sites/vite_detect.py. NULL for every row created before this
migration; the API/service layer treat it as optional throughout.

Revision ID: 1c98347a83ae
Revises: a692f4d3105b
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1c98347a83ae"
down_revision: Union[str, Sequence[str], None] = "a692f4d3105b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("static_site_deployments", "framework"):
        op.add_column(
            "static_site_deployments",
            sa.Column("framework", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    if _has_column("static_site_deployments", "framework"):
        op.drop_column("static_site_deployments", "framework")
