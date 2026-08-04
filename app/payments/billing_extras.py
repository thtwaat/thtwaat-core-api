"""Billing coupons, webhook idempotency, quota snapshots."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session

from app.models.base import Base, TimestampMixin


class BillingCoupon(Base, TimestampMixin):
    __tablename__ = "billing_coupons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    percent_off = Column(Numeric(5, 2), nullable=True)
    amount_off = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    duration = Column(String(32), nullable=False, default="once")  # once|repeating|forever
    max_redemptions = Column(Integer, nullable=True)
    redeemed_count = Column(Integer, nullable=False, default=0)
    stripe_coupon_id = Column(String(255), nullable=True)
    razorpay_offer_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)


class BillingWebhookEvent(Base, TimestampMixin):
    __tablename__ = "billing_webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(32), nullable=False, index=True)
    event_id = Column(String(255), nullable=False)
    event_type = Column(String(128), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    processed = Column(Boolean, nullable=False, default=False)
    processing_error = Column(Text, nullable=True)


class BillingQuotaSnapshot(Base, TimestampMixin):
    __tablename__ = "billing_quota_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    plan_key = Column(String(50), nullable=False)
    usage = Column(JSONB, nullable=False, default=dict)
    limits = Column(JSONB, nullable=False, default=dict)
    estimated_cost = Column(Numeric(12, 6), nullable=False, default=0)


def claim_webhook_event(
    db: Session,
    *,
    provider: str,
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> Optional[BillingWebhookEvent]:
    """
    Idempotent claim. Returns row if this process should handle it;
    returns None if already processed/claimed.
    """
    existing = (
        db.query(BillingWebhookEvent)
        .filter(
            BillingWebhookEvent.provider == provider,
            BillingWebhookEvent.event_id == event_id,
        )
        .first()
    )
    if existing:
        return None if existing.processed else existing

    row = BillingWebhookEvent(
        provider=provider,
        event_id=event_id,
        event_type=event_type,
        payload=payload or {},
        processed=False,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        return None


def mark_webhook_processed(db: Session, row: BillingWebhookEvent, error: Optional[str] = None) -> None:
    row.processed = True
    row.processing_error = error
    db.commit()


def get_active_coupon(db: Session, code: str) -> Optional[BillingCoupon]:
    coupon = (
        db.query(BillingCoupon)
        .filter(BillingCoupon.code == code.strip().upper(), BillingCoupon.is_active.is_(True))
        .first()
    )
    if not coupon:
        return None
    now = datetime.now(timezone.utc)
    if coupon.valid_from and coupon.valid_from > now:
        return None
    if coupon.valid_until and coupon.valid_until < now:
        return None
    if coupon.max_redemptions is not None and int(coupon.redeemed_count or 0) >= int(coupon.max_redemptions):
        return None
    return coupon


def apply_coupon_discount(amount: Decimal, coupon: BillingCoupon) -> Decimal:
    base = Decimal(str(amount or 0))
    if coupon.percent_off is not None:
        discounted = base * (Decimal("1") - (Decimal(str(coupon.percent_off)) / Decimal("100")))
        return max(Decimal("0"), discounted.quantize(Decimal("0.01")))
    if coupon.amount_off is not None:
        return max(Decimal("0"), (base - Decimal(str(coupon.amount_off))).quantize(Decimal("0.01")))
    return base
