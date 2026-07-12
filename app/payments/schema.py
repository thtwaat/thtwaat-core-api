"""
app/payments/schema.py

Pydantic schemas for the Payments module.
"""
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, condecimal

from app.payments.model import PaymentStatus, PaymentMethod, Gateway


class PaymentCreate(BaseModel):
    app_id: Optional[uuid.UUID] = None
    amount: condecimal(max_digits=10, decimal_places=2, gt=0) # type: ignore
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_method: PaymentMethod
    gateway: Gateway
    invoice_number: Optional[str] = Field(None, max_length=255)
    payment_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")


class PaymentUpdateStatus(BaseModel):
    status: PaymentStatus
    gateway_transaction_id: Optional[str] = None
    payment_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")


class PaymentResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    app_id: Optional[uuid.UUID]
    
    amount: float
    currency: str
    
    payment_method: PaymentMethod
    gateway: Gateway
    gateway_transaction_id: Optional[str]
    invoice_number: Optional[str]
    
    status: PaymentStatus
    payment_metadata: Optional[Dict[str, Any]] = None
    
    paid_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
