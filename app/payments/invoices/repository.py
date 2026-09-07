"""
app/payments/invoices/repository.py
"""
import uuid
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.payments.invoices.model import Invoice


class InvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Invoice:
        invoice = Invoice(**data)
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def create_idempotent_by_payment_id(self, data: dict) -> Tuple[Invoice, bool]:
        """Get-or-create keyed by ``provider_payment_id``.

        Financial ledger identity for a payment must never depend on which
        caller (a webhook handler vs. a client-triggered verify endpoint) or
        how many times (retry, duplicate delivery, concurrent race) happens
        to run first. A pre-check catches the common case cheaply; the
        surrounding ``IntegrityError`` catch is the real guarantee — it
        relies on the DB-level unique index on ``provider_payment_id`` (see
        the Alembic migration) so two concurrent callers can never both
        insert an invoice for the same payment, even if both pass the
        pre-check before either commits.

        Returns ``(invoice, created)`` — ``created`` is False whenever an
        invoice for this payment id already existed (found via the
        pre-check or recovered after losing the race), so callers can gate
        non-idempotent side effects (e.g. crediting an account) on it.
        """
        provider_payment_id = data.get("provider_payment_id")
        if provider_payment_id:
            existing = self.get_by_provider_payment_id(provider_payment_id)
            if existing:
                return existing, False

        invoice = Invoice(**data)
        self.db.add(invoice)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if provider_payment_id:
                existing = self.get_by_provider_payment_id(provider_payment_id)
                if existing:
                    return existing, False
            raise
        self.db.refresh(invoice)
        return invoice, True

    def get_by_id(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        return self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        ).scalar_one_or_none()

    def get_by_provider_id(self, provider_invoice_id: str) -> Optional[Invoice]:
        return self.db.execute(
            select(Invoice).where(Invoice.provider_invoice_id == provider_invoice_id)
        ).scalar_one_or_none()

    def get_by_provider_payment_id(self, provider_payment_id: str) -> Optional[Invoice]:
        return self.db.execute(
            select(Invoice).where(Invoice.provider_payment_id == provider_payment_id)
        ).scalar_one_or_none()

    def list_by_company(self, company_id: uuid.UUID, skip: int = 0, limit: int = 50) -> List[Invoice]:
        return list(self.db.execute(
            select(Invoice)
            .where(Invoice.company_id == company_id)
            .order_by(Invoice.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).scalars().all())

    def update(self, invoice: Invoice, data: dict) -> Invoice:
        for key, value in data.items():
            setattr(invoice, key, value)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice
