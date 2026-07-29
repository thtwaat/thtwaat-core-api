"""
app/payments/invoices/repository.py
"""
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
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

    def get_by_id(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        return self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        ).scalar_one_or_none()

    def get_by_provider_id(self, provider_invoice_id: str) -> Optional[Invoice]:
        return self.db.execute(
            select(Invoice).where(Invoice.provider_invoice_id == provider_invoice_id)
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
