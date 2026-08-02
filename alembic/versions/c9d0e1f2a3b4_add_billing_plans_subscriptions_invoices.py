"""Add billing plans, subscriptions, and invoices tables.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

subscription_provider = postgresql.ENUM(
    "stripe",
    "razorpay",
    "manual",
    name="subscription_provider_enum",
    create_type=False,
)
subscription_status = postgresql.ENUM(
    "trialing",
    "active",
    "past_due",
    "unpaid",
    "cancelled",
    "incomplete",
    name="subscription_status_enum",
    create_type=False,
)
invoice_status = postgresql.ENUM(
    "draft",
    "open",
    "paid",
    "void",
    "uncollectible",
    name="invoice_status_enum",
    create_type=False,
)


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


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


def _has_fk(table: str, fk_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return fk_name in {fk["name"] for fk in inspector.get_foreign_keys(table)}


def _timestamps():
    return [
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
    ]


def upgrade() -> None:
    subscription_provider.create(op.get_bind(), checkfirst=True)
    subscription_status.create(op.get_bind(), checkfirst=True)
    invoice_status.create(op.get_bind(), checkfirst=True)

    if not _has_table("plans"):
        op.create_table(
            "plans",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("stripe_product_id", sa.String(length=255), nullable=True),
            sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
            sa.Column("razorpay_plan_id", sa.String(length=255), nullable=True),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("interval", sa.String(length=20), nullable=False, server_default="month"),
            sa.Column("interval_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_users", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("max_apps", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("ai_credits", sa.Numeric(10, 4), nullable=False, server_default="100.0"),
            sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("max_agents", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_messages", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("max_tokens", sa.BigInteger(), nullable=False, server_default="50000"),
            sa.Column("max_storage", sa.BigInteger(), nullable=False, server_default="104857600"),
            sa.Column("max_domains", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_team_members", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("max_api_keys", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_templates", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("name", name="uq_plans_name"),
            *_timestamps(),
        )
        op.create_index("ix_plans_id", "plans", ["id"])
    else:
        # Backfill usage-limit columns if an older plans table already exists.
        plan_cols = [
            ("max_agents", sa.Integer(), "1"),
            ("max_messages", sa.Integer(), "100"),
            ("max_tokens", sa.BigInteger(), "50000"),
            ("max_storage", sa.BigInteger(), "104857600"),
            ("max_domains", sa.Integer(), "0"),
            ("max_team_members", sa.Integer(), "5"),
            ("max_api_keys", sa.Integer(), "1"),
            ("max_templates", sa.Integer(), "0"),
        ]
        for name, col_type, default in plan_cols:
            if not _has_column("plans", name):
                op.add_column(
                    "plans",
                    sa.Column(name, col_type, nullable=False, server_default=default),
                )

    if not _has_table("subscriptions"):
        # Create without invoice_id FK first (circular dependency with invoices).
        op.create_table(
            "subscriptions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "company_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "plan_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("plans.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("provider", subscription_provider, nullable=False),
            sa.Column("provider_customer_id", sa.String(length=255), nullable=True),
            sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
            sa.Column("payment_id", sa.String(length=255), nullable=True),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "status",
                subscription_status,
                nullable=False,
                server_default="incomplete",
            ),
            sa.Column(
                "cancel_at_period_end",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "subscription_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            *_timestamps(),
        )
        op.create_index("ix_subscriptions_id", "subscriptions", ["id"])
        op.create_index("ix_subscriptions_company_id", "subscriptions", ["company_id"])
        op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
        op.create_index(
            "ix_subscriptions_provider_customer_id",
            "subscriptions",
            ["provider_customer_id"],
        )
        op.create_index(
            "ix_subscriptions_provider_subscription_id",
            "subscriptions",
            ["provider_subscription_id"],
            unique=True,
        )

    if not _has_table("invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "company_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "subscription_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("provider_invoice_id", sa.String(length=255), nullable=True),
            sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
            sa.Column("amount_due", sa.Numeric(10, 2), nullable=False),
            sa.Column(
                "amount_paid",
                sa.Numeric(10, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("status", invoice_status, nullable=False, server_default="open"),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("invoice_pdf", sa.String(length=1000), nullable=True),
            sa.Column("hosted_url", sa.String(length=1000), nullable=True),
            sa.Column(
                "invoice_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            *_timestamps(),
        )
        op.create_index("ix_invoices_id", "invoices", ["id"])
        op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
        op.create_index(
            "ix_invoices_provider_invoice_id",
            "invoices",
            ["provider_invoice_id"],
            unique=True,
        )

    # Close the circular FK: subscriptions.invoice_id → invoices.id
    if (
        _has_table("subscriptions")
        and _has_table("invoices")
        and _has_column("subscriptions", "invoice_id")
        and not _has_fk("subscriptions", "fk_subscriptions_invoice_id")
    ):
        op.create_foreign_key(
            "fk_subscriptions_invoice_id",
            "subscriptions",
            "invoices",
            ["invoice_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if _has_table("subscriptions") and _has_fk("subscriptions", "fk_subscriptions_invoice_id"):
        op.drop_constraint(
            "fk_subscriptions_invoice_id",
            "subscriptions",
            type_="foreignkey",
        )

    if _has_table("invoices"):
        if _has_index("invoices", "ix_invoices_provider_invoice_id"):
            op.drop_index("ix_invoices_provider_invoice_id", table_name="invoices")
        if _has_index("invoices", "ix_invoices_company_id"):
            op.drop_index("ix_invoices_company_id", table_name="invoices")
        if _has_index("invoices", "ix_invoices_id"):
            op.drop_index("ix_invoices_id", table_name="invoices")
        op.drop_table("invoices")

    if _has_table("subscriptions"):
        for name in (
            "ix_subscriptions_provider_subscription_id",
            "ix_subscriptions_provider_customer_id",
            "ix_subscriptions_plan_id",
            "ix_subscriptions_company_id",
            "ix_subscriptions_id",
        ):
            if _has_index("subscriptions", name):
                op.drop_index(name, table_name="subscriptions")
        op.drop_table("subscriptions")

    if _has_table("plans"):
        if _has_index("plans", "ix_plans_id"):
            op.drop_index("ix_plans_id", table_name="plans")
        op.drop_table("plans")

    invoice_status.drop(op.get_bind(), checkfirst=True)
    subscription_status.drop(op.get_bind(), checkfirst=True)
    subscription_provider.drop(op.get_bind(), checkfirst=True)
