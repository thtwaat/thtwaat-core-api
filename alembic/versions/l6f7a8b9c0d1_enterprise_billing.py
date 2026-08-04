"""Enterprise billing additive tables and plan quota columns.

Revision ID: l6f7a8b9c0d1
Revises: k5e6f7a8b9c0
Create Date: 2026-08-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "l6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "k5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if _has_table("plans"):
        for name, col in [
            ("yearly_amount", sa.Column("yearly_amount", sa.Numeric(10, 2), nullable=True)),
            ("trial_days", sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0")),
            ("max_workspaces", sa.Column("max_workspaces", sa.Integer(), nullable=False, server_default="1")),
            ("max_widgets", sa.Column("max_widgets", sa.Integer(), nullable=False, server_default="1")),
            ("max_knowledge", sa.Column("max_knowledge", sa.Integer(), nullable=False, server_default="1")),
            ("stripe_yearly_price_id", sa.Column("stripe_yearly_price_id", sa.String(255), nullable=True)),
            ("razorpay_yearly_plan_id", sa.Column("razorpay_yearly_plan_id", sa.String(255), nullable=True)),
        ]:
            if not _has_column("plans", name):
                op.add_column("plans", col)

    if _has_table("company_usage_meters") and not _has_column("company_usage_meters", "estimated_cost"):
        op.add_column(
            "company_usage_meters",
            sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=False, server_default="0"),
        )
    if _has_table("company_usage_meters") and not _has_column("company_usage_meters", "max_widgets"):
        op.add_column(
            "company_usage_meters",
            sa.Column("max_widgets", sa.Integer(), nullable=False, server_default="1"),
        )
    if _has_table("company_usage_meters") and not _has_column("company_usage_meters", "max_knowledge"):
        op.add_column(
            "company_usage_meters",
            sa.Column("max_knowledge", sa.Integer(), nullable=False, server_default="1"),
        )

    if not _has_table("billing_coupons"):
        op.create_table(
            "billing_coupons",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("percent_off", sa.Numeric(5, 2), nullable=True),
            sa.Column("amount_off", sa.Numeric(10, 2), nullable=True),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("duration", sa.String(32), nullable=False, server_default="once"),
            sa.Column("max_redemptions", sa.Integer(), nullable=True),
            sa.Column("redeemed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stripe_coupon_id", sa.String(255), nullable=True),
            sa.Column("razorpay_offer_id", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("code", name="uq_billing_coupons_code"),
        )

    if not _has_table("billing_webhook_events"):
        op.create_table(
            "billing_webhook_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("event_id", sa.String(255), nullable=False),
            sa.Column("event_type", sa.String(128), nullable=False),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("processing_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("provider", "event_id", name="uq_billing_webhook_provider_event"),
        )
        op.create_index("ix_billing_webhook_events_type", "billing_webhook_events", ["event_type"])

    if not _has_table("billing_quota_snapshots"):
        op.create_table(
            "billing_quota_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("plan_key", sa.String(50), nullable=False),
            sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("limits", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_billing_quota_snapshots_company", "billing_quota_snapshots", ["company_id"])


def downgrade() -> None:
    pass
