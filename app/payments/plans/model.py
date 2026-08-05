"""
app/payments/plans/model.py

SQLAlchemy model for subscription Plans.
"""
import uuid
from sqlalchemy import Column, String, Boolean, Integer, Numeric, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, TimestampMixin

class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)

    # Stripe
    stripe_product_id = Column(String(255), nullable=True)
    stripe_price_id = Column(String(255), nullable=True)

    # Razorpay
    razorpay_plan_id = Column(String(255), nullable=True)

    # Pricing
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    interval = Column(String(20), nullable=False, default="month")  # month, year
    interval_count = Column(Integer, nullable=False, default=1)

    # Entitlements
    max_users = Column(Integer, nullable=False, default=5)
    max_apps = Column(Integer, nullable=False, default=1)
    ai_credits = Column(Numeric(10, 4), nullable=False, default=100.0)
    features = Column(JSONB, nullable=True, default=list)  # List of feature strings

    # Usage meter limits (Task 29)
    max_agents = Column(Integer, nullable=False, default=1)
    max_messages = Column(Integer, nullable=False, default=100)
    max_tokens = Column(BigInteger, nullable=False, default=50000)
    max_storage = Column(BigInteger, nullable=False, default=104857600)  # bytes
    max_domains = Column(Integer, nullable=False, default=0)
    max_team_members = Column(Integer, nullable=False, default=5)
    max_api_keys = Column(Integer, nullable=False, default=1)
    max_templates = Column(Integer, nullable=False, default=0)

    # Phase 6 additive entitlements
    yearly_amount = Column(Numeric(10, 2), nullable=True)
    trial_days = Column(Integer, nullable=False, default=0)
    max_workspaces = Column(Integer, nullable=False, default=1)
    max_widgets = Column(Integer, nullable=False, default=1)
    max_knowledge = Column(Integer, nullable=False, default=1)
    stripe_yearly_price_id = Column(String(255), nullable=True)
    razorpay_yearly_plan_id = Column(String(255), nullable=True)

    # Region pricing (India INR / International USD) — amount remains primary for compat
    price_inr = Column(Numeric(12, 2), nullable=True)
    price_usd = Column(Numeric(12, 2), nullable=True)
    yearly_price_inr = Column(Numeric(12, 2), nullable=True)
    yearly_price_usd = Column(Numeric(12, 2), nullable=True)
    is_custom_pricing = Column(Boolean, nullable=False, default=False)

    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Plan id={self.id} name={self.name!r} amount={self.amount}>"
