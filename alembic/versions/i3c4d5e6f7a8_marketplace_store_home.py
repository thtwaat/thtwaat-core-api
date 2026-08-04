"""Marketplace Store Home: media fields, category meta, collections, events.

Revision ID: i3c4d5e6f7a8
Revises: h2b3c4d5e6f7
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "h2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_CATEGORIES = (
    "insurance",
    "government",
    "travel",
    "retail",
    "manufacturing",
    "sales",
    "erp",
    "bi",
    "devops",
    "security",
    "news",
    "media",
    "startup",
    "productivity",
    "automation",
    "multilingual",
)


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return index_name in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    for value in NEW_CATEGORIES:
        bind.execute(
            sa.text(
                "DO $$ BEGIN "
                f"ALTER TYPE template_category_enum ADD VALUE IF NOT EXISTS '{value}'; "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "WHEN undefined_object THEN NULL; END $$;"
            )
        )

    if _has_table("marketplace_templates"):
        additive_cols = [
            ("banner_url", sa.Column("banner_url", sa.String(500), nullable=True)),
            ("screenshots", sa.Column("screenshots", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}")),
            ("video_url", sa.Column("video_url", sa.String(500), nullable=True)),
            ("live_demo_url", sa.Column("live_demo_url", sa.String(500), nullable=True)),
            ("discount_percent", sa.Column("discount_percent", sa.Integer(), nullable=True)),
            ("estimated_install_minutes", sa.Column("estimated_install_minutes", sa.Integer(), nullable=True)),
            ("compatibility", sa.Column("compatibility", sa.String(255), nullable=True)),
            ("is_editors_choice", sa.Column("is_editors_choice", sa.Boolean(), nullable=False, server_default=sa.text("false"))),
        ]
        for name, col in additive_cols:
            if not _has_column("marketplace_templates", name):
                op.add_column("marketplace_templates", col)
        if not _has_index("marketplace_templates", "ix_marketplace_templates_editors_choice"):
            op.create_index(
                "ix_marketplace_templates_editors_choice",
                "marketplace_templates",
                ["is_editors_choice", "status"],
            )

    if not _has_table("marketplace_category_meta"):
        op.create_table(
            "marketplace_category_meta",
            sa.Column("category_slug", sa.String(64), primary_key=True),
            sa.Column("display_name", sa.String(120), nullable=True),
            sa.Column("icon", sa.String(120), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("popularity_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if not _has_table("marketplace_collections"):
        op.create_table(
            "marketplace_collections",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("slug", sa.String(120), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("icon", sa.String(120), nullable=True),
            sa.Column("banner_url", sa.String(500), nullable=True),
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("collection_type", sa.String(32), nullable=False, server_default="curated"),
            sa.Column("computed_rule", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("slug", name="uq_marketplace_collections_slug"),
        )
        op.create_index("ix_marketplace_collections_featured", "marketplace_collections", ["is_featured", "is_public"])

    if not _has_table("marketplace_collection_items"):
        op.create_table(
            "marketplace_collection_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "collection_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_collections.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "template_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("collection_id", "template_id", name="uq_marketplace_collection_template"),
        )
        op.create_index(
            "ix_marketplace_collection_items_order",
            "marketplace_collection_items",
            ["collection_id", "position"],
        )

    if not _has_table("marketplace_template_events"):
        op.create_table(
            "marketplace_template_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "company_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "template_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(32), nullable=False, server_default="view"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index(
            "ix_marketplace_template_events_user_type",
            "marketplace_template_events",
            ["company_id", "user_id", "event_type", "created_at"],
        )


def downgrade() -> None:
    # Additive-only migration: keep tables/columns for safety; no drops.
    pass
