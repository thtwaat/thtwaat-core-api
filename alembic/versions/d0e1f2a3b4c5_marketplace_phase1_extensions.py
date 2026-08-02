"""Marketplace Phase 1: kind, pricing_tier, favorites, category expansion.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_CATEGORIES = (
    "writing",
    "coding",
    "marketing",
    "hr",
    "research",
    "ai_agents",
    "business",
    "analytics",
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

    # Expand category enum (idempotent ADD VALUE)
    for value in NEW_CATEGORIES:
        bind.execute(
            sa.text(
                "DO $$ BEGIN "
                f"ALTER TYPE template_category_enum ADD VALUE IF NOT EXISTS '{value}'; "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "WHEN undefined_object THEN NULL; END $$;"
            )
        )

    template_kind = postgresql.ENUM(
        "package",
        "prompt",
        "agent",
        name="template_kind_enum",
        create_type=False,
    )
    pricing_tier = postgresql.ENUM(
        "free",
        "starter",
        "pro",
        "enterprise",
        name="template_pricing_tier_enum",
        create_type=False,
    )
    template_kind.create(bind, checkfirst=True)
    pricing_tier.create(bind, checkfirst=True)

    if _has_table("marketplace_templates"):
        if not _has_column("marketplace_templates", "kind"):
            op.add_column(
                "marketplace_templates",
                sa.Column(
                    "kind",
                    template_kind,
                    nullable=False,
                    server_default="package",
                ),
            )
        if not _has_column("marketplace_templates", "pricing_tier"):
            op.add_column(
                "marketplace_templates",
                sa.Column(
                    "pricing_tier",
                    pricing_tier,
                    nullable=False,
                    server_default="free",
                ),
            )
        if not _has_index("marketplace_templates", "ix_marketplace_templates_kind_status"):
            op.create_index(
                "ix_marketplace_templates_kind_status",
                "marketplace_templates",
                ["kind", "status"],
            )
        if not _has_index("marketplace_templates", "ix_marketplace_templates_tags_gin"):
            op.create_index(
                "ix_marketplace_templates_tags_gin",
                "marketplace_templates",
                ["tags"],
                postgresql_using="gin",
            )

    if not _has_table("marketplace_template_favorites"):
        op.create_table(
            "marketplace_template_favorites",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
            sa.UniqueConstraint(
                "company_id",
                "user_id",
                "template_id",
                name="uq_marketplace_favorite_company_user_template",
            ),
        )
        op.create_index(
            "ix_marketplace_template_favorites_id",
            "marketplace_template_favorites",
            ["id"],
        )
        op.create_index(
            "ix_marketplace_template_favorites_company_id",
            "marketplace_template_favorites",
            ["company_id"],
        )
        op.create_index(
            "ix_marketplace_template_favorites_user_id",
            "marketplace_template_favorites",
            ["user_id"],
        )
        op.create_index(
            "ix_marketplace_template_favorites_template_id",
            "marketplace_template_favorites",
            ["template_id"],
        )
        op.create_index(
            "ix_marketplace_favorites_user",
            "marketplace_template_favorites",
            ["company_id", "user_id"],
        )


def downgrade() -> None:
    if _has_table("marketplace_template_favorites"):
        op.drop_table("marketplace_template_favorites")

    if _has_table("marketplace_templates"):
        if _has_index("marketplace_templates", "ix_marketplace_templates_tags_gin"):
            op.drop_index("ix_marketplace_templates_tags_gin", table_name="marketplace_templates")
        if _has_index("marketplace_templates", "ix_marketplace_templates_kind_status"):
            op.drop_index("ix_marketplace_templates_kind_status", table_name="marketplace_templates")
        if _has_column("marketplace_templates", "pricing_tier"):
            op.drop_column("marketplace_templates", "pricing_tier")
        if _has_column("marketplace_templates", "kind"):
            op.drop_column("marketplace_templates", "kind")

    op.execute("DROP TYPE IF EXISTS template_pricing_tier_enum")
    op.execute("DROP TYPE IF EXISTS template_kind_enum")
    # Postgres cannot easily remove enum values; leave template_category_enum additions.
