"""
app/payments/subscriptions/schema.py
"""
import uuid
from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.payments.subscriptions.model import SubscriptionStatus, SubscriptionProvider


class StripeCheckoutRequest(BaseModel):
    plan_id: uuid.UUID
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str  = Field(..., description="URL to redirect if user cancels")


class RazorpayCheckoutRequest(BaseModel):
    plan_id: uuid.UUID
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: uuid.UUID


class CheckoutSessionResponse(BaseModel):
    checkout_url: Optional[str] = None
    order_id: Optional[str] = None
    subscription_id: Optional[uuid.UUID] = None
    provider: str


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    plan_id: uuid.UUID
    provider: SubscriptionProvider
    provider_customer_id: Optional[str]
    provider_subscription_id: Optional[str]
    payment_id: Optional[str]
    invoice_id: Optional[uuid.UUID]
    status: SubscriptionStatus
    cancel_at_period_end: bool
    cancelled_at: Optional[datetime]
    trial_end: Optional[datetime]
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
