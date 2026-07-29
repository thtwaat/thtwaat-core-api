"""
app/payments/subscriptions/model.py

SQLAlchemy model for Subscriptions.
A Subscription links a Company to a Plan via a payment provider.
"""
import uuid
import enum
from sqlalchemy import Column, String, Boolean, Enum as SAEnum, ForeignKey, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin


class SubscriptionStatus(str, enum.Enum):
    TRIALING   = "trialing"
    ACTIVE     = "active"
    PAST_DUE   = "past_due"
    UNPAID     = "unpaid"
    CANCELLED  = "cancelled"
    INCOMPLETE = "incomplete"


class SubscriptionProvider(str, enum.Enum):
    STRIPE   = "stripe"
    RAZORPAY = "razorpay"
    MANUAL   = "manual"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)

    # Tenant
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id    = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Payment provider linkage
    provider                 = Column(SAEnum(SubscriptionProvider, name="subscription_provider_enum"), nullable=False)
    provider_customer_id     = Column(String(255), nullable=True, index=True)  # Stripe customer / Razorpay contact
    provider_subscription_id = Column(String(255), nullable=True, index=True, unique=True)  # Stripe sub / Razorpay sub
    payment_id               = Column(String(255), nullable=True)   # Last associated payment/order ID
    invoice_id               = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL", use_alter=True, name="fk_subscriptions_invoice_id"), nullable=True)  # Latest invoice

    # State
    status               = Column(SAEnum(SubscriptionStatus, name="subscription_status_enum"), nullable=False, default=SubscriptionStatus.INCOMPLETE)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    cancelled_at         = Column(DateTime(timezone=True), nullable=True)
    trial_end            = Column(DateTime(timezone=True), nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end   = Column(DateTime(timezone=True), nullable=True)

    metadata_             = Column("subscription_metadata", JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} company={self.company_id} status={self.status}>"
