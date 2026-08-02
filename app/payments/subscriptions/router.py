"""
app/payments/subscriptions/router.py
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.payments.subscriptions.schema import (
    StripeCheckoutRequest, RazorpayCheckoutRequest, RazorpayVerifyRequest,
    CheckoutSessionResponse, SubscriptionResponse
)
from app.payments.subscriptions.service import SubscriptionService

router = APIRouter(prefix="/payments/subscriptions", tags=["Subscriptions"])


def get_sub_service(db: Session = Depends(get_db)) -> SubscriptionService:
    return SubscriptionService(db)


@router.post(
    "/stripe/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Stripe Checkout Session for a plan",
)
def create_stripe_checkout(
    payload: StripeCheckoutRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    """
    Creates a Stripe Checkout Session. Returns a `checkout_url` the frontend
    should redirect the user to for payment.
    """
    return service.create_stripe_checkout_session(current_user.company_id, payload)


@router.post(
    "/razorpay/order",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Razorpay order for a plan",
)
def create_razorpay_order(
    payload: RazorpayCheckoutRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    """
    Creates a Razorpay order. The frontend uses the returned `order_id` with
    the Razorpay JS SDK to open the payment popup.
    """
    return service.create_razorpay_order(current_user.company_id, payload)


@router.post(
    "/razorpay/verify",
    response_model=SubscriptionResponse,
    summary="Verify Razorpay payment signature and activate subscription",
)
def verify_razorpay_payment(
    payload: RazorpayVerifyRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    """
    Verifies the Razorpay HMAC-SHA256 signature from the frontend callback,
    then activates the subscription and updates the company plan.
    """
    return service.verify_razorpay_payment(current_user.company_id, payload)


@router.get(
    "/me",
    response_model=Optional[SubscriptionResponse],
    summary="Get current company's active subscription",
)
def get_my_subscription(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    """Returns the active subscription for the authenticated user's company."""
    return service.get_subscription(current_user.company_id)


@router.get(
    "/",
    response_model=List[SubscriptionResponse],
    summary="List subscriptions for the current company",
)
@router.get(
    "/history",
    response_model=List[SubscriptionResponse],
    summary="Get all subscriptions for the current company",
)
def list_subscriptions(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    return service.list_subscriptions(current_user.company_id)


@router.post(
    "/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel current Stripe subscription at period end",
)
def cancel_subscription(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    """
    Sets cancel_at_period_end=True on the active Stripe subscription.
    The subscription remains active until the end of the billing period.
    """
    return service.cancel_stripe_subscription(current_user.company_id)
