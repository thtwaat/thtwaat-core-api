"""
app/payments/invoices/service.py
"""
import uuid
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.payments.invoices.model import Invoice
from app.payments.invoices.repository import InvoiceRepository


class InvoiceService:
    def __init__(self, db: Session):
        self.repo = InvoiceRepository(db)

    def get_invoice(self, invoice_id: uuid.UUID, company_id: uuid.UUID) -> Invoice:
        invoice = self.repo.get_by_id(invoice_id)
        if not invoice or invoice.company_id != company_id:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        return invoice

    def list_invoices(self, company_id: uuid.UUID, skip: int = 0, limit: int = 50) -> List[Invoice]:
        return self.repo.list_by_company(company_id, skip=skip, limit=limit)
