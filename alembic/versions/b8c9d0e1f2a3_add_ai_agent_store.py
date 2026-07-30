"""add ai agent store

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

publisher_status = sa.Enum(
    "active", "suspended", "pending",
    name="agent_store_publisher_status_enum",
)
listing_status = sa.Enum(
    "draft", "pending_review", "published", "suspended", "rejected",
    name="agent_store_listing_status_enum",
)
pricing_model = sa.Enum(
    "free", "one_time", "subscription",
    name="agent_store_pricing_model_enum",
)
purchase_status = sa.Enum(
    "pending", "completed", "refunded", "failed",
    name="agent_store_purchase_status_enum",
)
abuse_status = sa.Enum(
    "open", "reviewing", "resolved", "dismissed",
    name="agent_store_abuse_status_enum",
)


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    publisher_status.create(op.get_bind(), checkfirst=True)
    listing_status.create(op.get_bind(), checkfirst=True)
    pricing_model.create(op.get_bind(), checkfirst=True)
    purchase_status.create(op.get_bind(), checkfirst=True)
    abuse_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "agent_store_publishers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", publisher_status, nullable=False, server_default="active"),
        sa.Column("payout_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revenue_share_bps", sa.Integer(), nullable=False, server_default="7000"),
        sa.UniqueConstraint("company_id", name="uq_agent_store_publisher_company"),
        sa.UniqueConstraint("slug", name="uq_agent_store_publisher_slug"),
        *_timestamps(),
    )
    op.create_index("ix_agent_store_publishers_company_id", "agent_store_publishers", ["company_id"])
    op.create_index("ix_agent_store_publishers_slug", "agent_store_publishers", ["slug"])

    op.create_table(
        "agent_store_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "publisher_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_store_publishers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketplace_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("short_description", sa.String(500), nullable=False, server_default=""),
        sa.Column("long_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("screenshots", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("demo_url", sa.String(500), nullable=True),
        sa.Column("supported_languages", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("knowledge_requirements", sa.Text(), nullable=True),
        sa.Column("categories", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("pricing_model", pricing_model, nullable=False, server_default="free"),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("status", listing_status, nullable=False, server_default="draft"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified_badge", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("install_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating_avg", sa.Numeric(3, 2), nullable=False, server_default="0"),
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "moderated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("moderation_notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("template_id", name="uq_agent_store_listing_template"),
        sa.UniqueConstraint("slug", name="uq_agent_store_listing_slug"),
        *_timestamps(),
    )
    op.create_index("ix_agent_store_listings_publisher_id", "agent_store_listings", ["publisher_id"])
    op.create_index("ix_agent_store_listings_template_id", "agent_store_listings", ["template_id"])
    op.create_index("ix_agent_store_listings_slug", "agent_store_listings", ["slug"])
    op.create_index("ix_agent_store_listings_source_agent_id", "agent_store_listings", ["source_agent_id"])
    op.create_index(
        "ix_agent_store_listings_status_featured",
        "agent_store_listings",
        ["status", "is_featured"],
    )
    op.create_index(
        "ix_agent_store_listings_trending",
        "agent_store_listings",
        ["install_count", "rating_avg"],
    )

    op.create_table(
        "agent_store_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_store_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("listing_id", "company_id", "user_id", name="uq_agent_store_review"),
        *_timestamps(),
    )
    op.create_index("ix_agent_store_reviews_listing_id", "agent_store_reviews", ["listing_id"])

    op.create_table(
        "agent_store_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_store_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "buyer_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "buyer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "installation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketplace_template_installations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("publisher_share", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("platform_share", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", purchase_status, nullable=False, server_default="pending"),
        sa.Column("pricing_model", sa.String(32), nullable=False, server_default="free"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )
    op.create_index("ix_agent_store_purchases_buyer", "agent_store_purchases", ["buyer_company_id"])
    op.create_index("ix_agent_store_purchases_listing", "agent_store_purchases", ["listing_id"])

    op.create_table(
        "agent_store_abuse_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_store_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reporter_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reporter_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", abuse_status, nullable=False, server_default="open"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_agent_store_abuse_reports_listing_id", "agent_store_abuse_reports", ["listing_id"])


def downgrade() -> None:
    op.drop_table("agent_store_abuse_reports")
    op.drop_table("agent_store_purchases")
    op.drop_table("agent_store_reviews")
    op.drop_table("agent_store_listings")
    op.drop_table("agent_store_publishers")
    abuse_status.drop(op.get_bind(), checkfirst=True)
    purchase_status.drop(op.get_bind(), checkfirst=True)
    pricing_model.drop(op.get_bind(), checkfirst=True)
    listing_status.drop(op.get_bind(), checkfirst=True)
    publisher_status.drop(op.get_bind(), checkfirst=True)
