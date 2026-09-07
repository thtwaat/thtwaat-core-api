"""Unique index on invoices.provider_payment_id (partial, non-null).

DB-enforced idempotency for the payment ledger: at most one invoice per real
provider payment id. Closes a duplicate-invoice bug where the Razorpay
payment.captured webhook and the client-triggered /razorpay/verify endpoint
could each independently create a PAID invoice for the same payment (the
webhook's own idempotency check queried the wrong column and never matched).

Safety note: if this environment already has duplicate provider_payment_id
values (a symptom of the bug above), creating this index will fail loudly
rather than silently leaving the duplicates in place. Run the duplicate-check
query in the docstring of `upgrade()` first and reconcile/void the extra
invoice rows before applying this migration to a database that predates the
fix.

Revision ID: m6a7b8c9d0e1
Revises: 27603ebdcff8
Create Date: 2026-09-07

Note: this originally pointed to down_revision "64a265978b92"
("ai_calling_quota"), which was never committed to this repository — it
existed only as an uncommitted, in-progress file in a shared working
directory at the time this migration was authored, so `alembic heads` on
that filesystem resolved to it as the apparent current head. From git's
history (and any clean checkout, CI run, or production deploy, which only
ever see committed files) that revision does not exist, breaking the chain.
The actual current head in committed history is `27603ebdcff8`
(preview_deployments) — corrected below. If/when `ai_calling_quota` is
committed on top of `27603ebdcff8` separately, it will become a sibling of
this migration rather than its parent, which is the correct relationship
since neither depends on the other's schema changes.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "27603ebdcff8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = "uq_invoices_provider_payment_id"


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return name in {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    """
    Before running against a database that predates the fix, check for
    pre-existing duplicates (this migration will fail with a Postgres
    uniqueness error if any are found, rather than silently dropping rows):

        SELECT provider_payment_id, count(*)
        FROM invoices
        WHERE provider_payment_id IS NOT NULL
        GROUP BY provider_payment_id
        HAVING count(*) > 1;
    """
    if not _has_table("invoices"):
        return
    if _has_index("invoices", _INDEX_NAME):
        return
    op.create_index(
        _INDEX_NAME,
        "invoices",
        ["provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )


def downgrade() -> None:
    if _has_index("invoices", _INDEX_NAME):
        op.drop_index(_INDEX_NAME, table_name="invoices")
