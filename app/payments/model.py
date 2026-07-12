"""
app/payments/model.py

SQLAlchemy models for Payments.
"""
import uuid
import enum
from sqlalchemy import Column, String, Numeric, Enum as SAEnum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentMethod(str, enum.Enum):
    CARD = "card"
    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"
    CASH = "cash"

class Gateway(str, enum.Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"
    PAYPAL = "paypal"
    MANUAL = "manual"

class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    
    # Relationships & Ownership
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id", ondelete="SET NULL"), index=True, nullable=True)

    # Financials
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    # Gateway Details
    payment_method = Column(SAEnum(PaymentMethod, name="payment_method_enum"), nullable=False)
    gateway = Column(SAEnum(Gateway, name="gateway_enum"), nullable=False)
    gateway_transaction_id = Column(String(255), nullable=True, index=True)
    invoice_number = Column(String(255), nullable=True, unique=True, index=True)
    
    # State
    status = Column(SAEnum(PaymentStatus, name="payment_status_enum"), default=PaymentStatus.PENDING, nullable=False)
    payment_metadata = Column(JSONB, nullable=True) # Used for storing gateway-specific extra data
    
    # Timestamps
    paid_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Payment id={self.id} amount={self.amount} {self.currency} status={self.status}>"
