"""
app/payments/subscriptions/router.py
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.payments.subscriptions.schema import (
    StripeCheckoutRequest, RazorpayCheckoutRequest, RazorpayVerifyRequest,
    CheckoutSessionResponse, SubscriptionResponse, ChangePlanRequest
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
    service: SubscriptionService = Depends(get_sub_service),
):
    """
    Active subscription for the company, or JSON ``null`` (HTTP 200).
    DB failures → 503 with a clear detail (not opaque 500).
    """
    import logging

    from sqlalchemy.exc import SQLAlchemyError

    log = logging.getLogger(__name__)
    try:
        sub = service.get_subscription(current_user.company_id)
    except SQLAlchemyError as exc:
        log.exception("GET /payments/subscriptions/me db error company=%s", current_user.company_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Billing data unavailable ({exc.__class__.__name__})",
        ) from exc

    if sub is None:
        return None

    try:
        return SubscriptionResponse.model_validate(sub)
    except Exception as exc:
        log.exception(
            "GET /payments/subscriptions/me serialize error sub=%s",
            getattr(sub, "id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subscription record could not be serialized",
        ) from exc


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
    summary="Cancel current subscription at period end",
)
def cancel_subscription(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    """
    Sets cancel_at_period_end=True on the active subscription (Stripe/Razorpay).
    The subscription remains active until the end of the billing period when supported.
    """
    return service.cancel_subscription(current_user.company_id)


@router.post(
    "/resume",
    response_model=SubscriptionResponse,
    summary="Resume a subscription pending cancellation",
)
def resume_subscription(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service),
):
    return service.resume_subscription(current_user.company_id)


@router.post(
    "/change-plan",
    response_model=CheckoutSessionResponse,
    summary="Upgrade or downgrade plan",
)
def change_plan(
    payload: ChangePlanRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service),
):
    return service.change_plan(current_user.company_id, payload)


@router.get("/providers")
def subscription_providers(
    current_user: UserProfileResponse = Depends(get_current_user),
):
    _ = current_user
    from app.payments.provider_flags import billing_providers_status

    return billing_providers_status()
