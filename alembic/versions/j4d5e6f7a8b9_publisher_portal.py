"""Publisher Portal additive fields: listing statuses, profile social, review replies.

Revision ID: j4d5e6f7a8b9
Revises: i3c4d5e6f7a8
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "i3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_LISTING_STATUSES = ("private", "archived")


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for value in NEW_LISTING_STATUSES:
        bind.execute(
            sa.text(
                "DO $$ BEGIN "
                f"ALTER TYPE agent_store_listing_status_enum ADD VALUE IF NOT EXISTS '{value}'; "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "WHEN undefined_object THEN NULL; END $$;"
            )
        )

    if _has_table("agent_store_publishers"):
        for name, col in [
            ("banner_url", sa.Column("banner_url", sa.String(500), nullable=True)),
            ("github_url", sa.Column("github_url", sa.String(500), nullable=True)),
            ("linkedin_url", sa.Column("linkedin_url", sa.String(500), nullable=True)),
            ("twitter_url", sa.Column("twitter_url", sa.String(500), nullable=True)),
            ("followers_count", sa.Column("followers_count", sa.Integer(), nullable=False, server_default="0")),
            ("following_count", sa.Column("following_count", sa.Integer(), nullable=False, server_default="0")),
        ]:
            if not _has_column("agent_store_publishers", name):
                op.add_column("agent_store_publishers", col)

    if _has_table("agent_store_reviews"):
        for name, col in [
            ("publisher_reply", sa.Column("publisher_reply", sa.Text(), nullable=True)),
            ("publisher_replied_at", sa.Column("publisher_replied_at", sa.DateTime(timezone=True), nullable=True)),
            ("helpful_count", sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0")),
        ]:
            if not _has_column("agent_store_reviews", name):
                op.add_column("agent_store_reviews", col)

    if _has_table("agent_store_listings") and not _has_column("agent_store_listings", "cover_url"):
        op.add_column("agent_store_listings", sa.Column("cover_url", sa.String(500), nullable=True))
    if _has_table("agent_store_listings") and not _has_column("agent_store_listings", "logo_url"):
        op.add_column("agent_store_listings", sa.Column("logo_url", sa.String(500), nullable=True))


def downgrade() -> None:
    pass
