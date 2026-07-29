"""
app/payments/invoices/schema.py
"""
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.payments.invoices.model import InvoiceStatus


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    subscription_id: Optional[uuid.UUID]
    provider: str
    provider_invoice_id: Optional[str]
    provider_payment_id: Optional[str]
    amount_due: float
    amount_paid: float
    currency: str
    status: InvoiceStatus
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    invoice_pdf: Optional[str]
    hosted_url: Optional[str]
    invoice_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
