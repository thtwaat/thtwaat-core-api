"""Additive region pricing columns on plans.

Revision ID: m7a8b9c0d1e2
Revises: l6f7a8b9c0d1
Create Date: 2026-08-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "l6f7a8b9c0d1"
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
    if not _has_table("plans"):
        return
    for name, col in [
        ("price_inr", sa.Column("price_inr", sa.Numeric(12, 2), nullable=True)),
        ("price_usd", sa.Column("price_usd", sa.Numeric(12, 2), nullable=True)),
        ("yearly_price_inr", sa.Column("yearly_price_inr", sa.Numeric(12, 2), nullable=True)),
        ("yearly_price_usd", sa.Column("yearly_price_usd", sa.Numeric(12, 2), nullable=True)),
        (
            "is_custom_pricing",
            sa.Column("is_custom_pricing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        ),
    ]:
        if not _has_column("plans", name):
            op.add_column("plans", col)

    # Backfill USD from legacy amount when price_usd is null
    op.execute(
        """
        UPDATE plans
        SET price_usd = amount
        WHERE price_usd IS NULL
        """
    )
    op.execute(
        """
        UPDATE plans
        SET yearly_price_usd = yearly_amount
        WHERE yearly_price_usd IS NULL AND yearly_amount IS NOT NULL
        """
    )


def downgrade() -> None:
    # Additive-only policy: leave columns in place for safety.
    pass
