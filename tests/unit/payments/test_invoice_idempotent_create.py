"""InvoiceRepository.create_idempotent_by_payment_id: get-or-create keyed by
provider_payment_id. This is the DB-enforced idempotency backstop for the
payment ledger (see the unique index added in
alembic/versions/m6a7b8c9d0e1_invoices_provider_payment_id_unique.py) — a
pre-check handles the common case cheaply, and an IntegrityError recovery
path proves this is safe even when two callers race past the pre-check
before either commits.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.payments.invoices.model import InvoiceStatus
from app.payments.invoices.repository import InvoiceRepository


def _repo():
    db = MagicMock()
    return InvoiceRepository(db=db), db


def _invoice_data(payment_id: str = "pay_1") -> dict:
    return {
        "company_id": uuid.uuid4(),
        "provider": "razorpay",
        "provider_payment_id": payment_id,
        "amount_due": 999,
        "amount_paid": 999,
        "currency": "INR",
        "status": InvoiceStatus.PAID,
    }


@pytest.mark.unit
def test_creates_new_invoice_when_none_exists():
    repo, db = _repo()
    repo.get_by_provider_payment_id = MagicMock(return_value=None)

    invoice, created = repo.create_idempotent_by_payment_id(_invoice_data("pay_new"))

    assert created is True
    assert invoice.provider_payment_id == "pay_new"
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@pytest.mark.unit
def test_precheck_finds_existing_invoice_and_skips_insert():
    repo, db = _repo()
    existing = MagicMock()
    repo.get_by_provider_payment_id = MagicMock(return_value=existing)

    invoice, created = repo.create_idempotent_by_payment_id(_invoice_data("pay_existing"))

    assert invoice is existing
    assert created is False
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.unit
def test_concurrent_race_recovers_the_winners_row_via_db_constraint():
    """Simulates two callers racing: both pass the pre-check (neither sees an
    existing invoice yet, e.g. the webhook and /razorpay/verify running at
    the same instant) — this caller's commit loses to the DB unique index and
    must recover the winner's row instead of crashing or silently dropping
    the payment."""
    repo, db = _repo()
    winner_invoice = MagicMock()
    # 1st call = the pre-check (race window: nothing there yet).
    # 2nd call = after the IntegrityError, re-fetch finds the winner's row.
    repo.get_by_provider_payment_id = MagicMock(side_effect=[None, winner_invoice])
    db.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate key"))

    invoice, created = repo.create_idempotent_by_payment_id(_invoice_data("pay_race"))

    assert invoice is winner_invoice
    assert created is False
    db.rollback.assert_called_once()


@pytest.mark.unit
def test_integrity_error_without_a_recoverable_row_reraises():
    """If the insert fails and there's still no invoice for this payment id
    after rollback, this is a real error (not a benign duplicate) and must
    propagate rather than being swallowed."""
    repo, db = _repo()
    repo.get_by_provider_payment_id = MagicMock(return_value=None)
    db.commit.side_effect = IntegrityError("INSERT", {}, Exception("some other constraint"))

    with pytest.raises(IntegrityError):
        repo.create_idempotent_by_payment_id(_invoice_data("pay_broken"))

    db.rollback.assert_called_once()


@pytest.mark.unit
def test_missing_payment_id_always_creates_without_precheck():
    """No provider_payment_id to key on (e.g. a manual/void row) — nothing to
    dedupe against, so this always inserts."""
    repo, db = _repo()
    data = _invoice_data()
    data["provider_payment_id"] = None
    repo.get_by_provider_payment_id = MagicMock()

    invoice, created = repo.create_idempotent_by_payment_id(data)

    assert created is True
    repo.get_by_provider_payment_id.assert_not_called()
    db.commit.assert_called_once()
