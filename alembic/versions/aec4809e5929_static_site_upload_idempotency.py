"""THTWAAT Deploy Phase 2 — static_site_upload_idempotency table.

Adds the Idempotency-Key -> deployment mapping used by
POST /api/v2/studio/static-sites/{id}/upload to make a retried/duplicated
upload request resolve to the same deployment instead of launching a second
Docker build (see app/static_sites/models.py::StaticSiteUploadIdempotency
and the Phase 2 staging validation report §6/§12). Purely additive — no
existing table or column is touched.

Revision ID: aec4809e5929
Revises: 1c98347a83ae
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "aec4809e5929"
down_revision: Union[str, Sequence[str], None] = "1c98347a83ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("static_site_upload_idempotency"):
        return
    op.create_table(
        "static_site_upload_idempotency",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("static_sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column(
            "deployment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("static_site_deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "idempotency_key", name="uq_static_site_idempotency_site_key"),
    )
    op.create_index(
        "ix_static_site_upload_idempotency_site_id", "static_site_upload_idempotency", ["site_id"]
    )
    op.create_index(
        "ix_static_site_idempotency_created_at", "static_site_upload_idempotency", ["created_at"]
    )


def downgrade() -> None:
    if not _has_table("static_site_upload_idempotency"):
        return
    op.drop_index("ix_static_site_idempotency_created_at", table_name="static_site_upload_idempotency")
    op.drop_index("ix_static_site_upload_idempotency_site_id", table_name="static_site_upload_idempotency")
    op.drop_table("static_site_upload_idempotency")
