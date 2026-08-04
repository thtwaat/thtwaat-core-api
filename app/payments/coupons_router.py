"""Billing coupons API — additive under /payments/coupons."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.payments.billing_extras import BillingCoupon, get_active_coupon
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/payments/coupons", tags=["Billing Coupons"])


class CouponCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = None
    percent_off: Optional[Decimal] = Field(None, ge=0, le=100)
    amount_off: Optional[Decimal] = Field(None, ge=0)
    currency: str = "USD"
    duration: str = Field(default="once", pattern="^(once|repeating|forever)$")
    max_redemptions: Optional[int] = Field(None, ge=1)
    stripe_coupon_id: Optional[str] = None
    razorpay_offer_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    description: Optional[str] = None
    percent_off: Optional[Decimal] = None
    amount_off: Optional[Decimal] = None
    currency: str
    duration: str
    max_redemptions: Optional[int] = None
    redeemed_count: int
    is_active: bool
    stripe_coupon_id: Optional[str] = None
    razorpay_offer_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CouponValidateRequest(BaseModel):
    code: str


def require_platform_admin(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.PLATFORM_ADMIN)(user.role)
    return user


@router.get("", response_model=List[CouponResponse])
def list_coupons(
    _: UserProfileResponse = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(BillingCoupon).order_by(BillingCoupon.created_at.desc()).limit(200).all()
    return rows


@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    payload: CouponCreate,
    _: UserProfileResponse = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    code = payload.code.strip().upper()
    if db.query(BillingCoupon).filter(BillingCoupon.code == code).first():
        raise HTTPException(status_code=409, detail="Coupon code already exists")
    if payload.percent_off is None and payload.amount_off is None:
        raise HTTPException(status_code=400, detail="percent_off or amount_off required")
    row = BillingCoupon(
        code=code,
        description=payload.description,
        percent_off=payload.percent_off,
        amount_off=payload.amount_off,
        currency=payload.currency.upper(),
        duration=payload.duration,
        max_redemptions=payload.max_redemptions,
        stripe_coupon_id=payload.stripe_coupon_id,
        razorpay_offer_id=payload.razorpay_offer_id,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/validate")
def validate_coupon(
    payload: CouponValidateRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    coupon = get_active_coupon(db, payload.code)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not valid")
    return {
        "valid": True,
        "code": coupon.code,
        "percent_off": float(coupon.percent_off) if coupon.percent_off is not None else None,
        "amount_off": float(coupon.amount_off) if coupon.amount_off is not None else None,
        "currency": coupon.currency,
        "duration": coupon.duration,
    }
