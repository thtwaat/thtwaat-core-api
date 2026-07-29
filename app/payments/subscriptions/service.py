"""
app/payments/subscriptions/service.py

Orchestrates subscription lifecycle for both Stripe and Razorpay.
"""
import uuid
import logging
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

import stripe

from app.config.settings import settings
from app.payments.plans.repository import PlanRepository
from app.payments.subscriptions.model import Subscription, SubscriptionStatus, SubscriptionProvider
from app.payments.subscriptions.schema import (
    StripeCheckoutRequest, RazorpayCheckoutRequest, RazorpayVerifyRequest,
    CheckoutSessionResponse, SubscriptionResponse
)
from app.payments.subscriptions.repository import SubscriptionRepository
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.invoices.repository import InvoiceRepository
from app.companies.repository import CompanyRepository
from app.companies.model import Company, CompanyPlan, CompanyStatus

logger = logging.getLogger(__name__)

# Map plan names (lowercase) -> CompanyPlan enum
# pro/business map onto growth/enterprise PG enum until enum is extended
PLAN_NAME_MAP = {
    "free": CompanyPlan.FREE,
    "starter": CompanyPlan.STARTER,
    "growth": CompanyPlan.GROWTH,
    "pro": CompanyPlan.GROWTH,
    "business": CompanyPlan.ENTERPRISE,
    "enterprise": CompanyPlan.ENTERPRISE,
}


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db
        self.sub_repo = SubscriptionRepository(db)
        self.plan_repo = PlanRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.company_repo = CompanyRepository(db)

    def _get_or_create_stripe_customer(self, company: Company) -> str:
        """Gets the existing Stripe customer_id for a company or creates one."""
        if company.stripe_customer_id:
            return company.stripe_customer_id
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe is not configured.")
        stripe.api_key = settings.STRIPE_SECRET_KEY
        customer = stripe.Customer.create(
            name=company.name,
            metadata={"company_id": str(company.id), "slug": company.slug}
        )
        # Persist customer id
        company.stripe_customer_id = customer.id
        self.db.commit()
        return customer.id

    # ─── Stripe ────────────────────────────────────────────────────────────

    def create_stripe_checkout_session(self, company_id: uuid.UUID, data: StripeCheckoutRequest) -> CheckoutSessionResponse:
        """Creates a Stripe Checkout Session for a plan subscription."""
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe is not configured.")
        stripe.api_key = settings.STRIPE_SECRET_KEY

        company = self.company_repo.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")

        plan = self.plan_repo.get_by_id(data.plan_id)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=404, detail="Plan not found or inactive.")

        if not plan.stripe_price_id:
            raise HTTPException(
                status_code=400,
                detail=f"Plan '{plan.name}' does not have a Stripe price configured. Ask admin to set stripe_price_id."
            )

        customer_id = self._get_or_create_stripe_customer(company)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            success_url=data.success_url,
            cancel_url=data.cancel_url,
            metadata={"company_id": str(company_id), "plan_id": str(plan.id)},
            subscription_data={"metadata": {"company_id": str(company_id), "plan_id": str(plan.id)}}
        )

        # Create a pending subscription record
        existing = self.sub_repo.get_active_by_company(company_id)
        if not existing:
            self.sub_repo.create({
                "company_id": company_id,
                "plan_id": plan.id,
                "provider": SubscriptionProvider.STRIPE,
                "provider_customer_id": customer_id,
                "status": SubscriptionStatus.INCOMPLETE,
                "metadata_": {"checkout_session_id": session.id}
            })

        return CheckoutSessionResponse(checkout_url=session.url, provider="stripe")

    def get_subscription(self, company_id: uuid.UUID) -> Optional[Subscription]:
        """Returns the active subscription for a company."""
        return self.sub_repo.get_active_by_company(company_id)

    def list_subscriptions(self, company_id: uuid.UUID) -> List[Subscription]:
        return self.sub_repo.list_by_company(company_id)

    def cancel_stripe_subscription(self, company_id: uuid.UUID) -> SubscriptionResponse:
        """Cancels an active Stripe subscription at period end."""
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe is not configured.")
        stripe.api_key = settings.STRIPE_SECRET_KEY

        sub = self.sub_repo.get_active_by_company(company_id)
        if not sub:
            raise HTTPException(status_code=404, detail="No active subscription found.")
        if sub.provider != SubscriptionProvider.STRIPE:
            raise HTTPException(status_code=400, detail="Subscription is not a Stripe subscription.")
        if not sub.provider_subscription_id:
            raise HTTPException(status_code=400, detail="No Stripe subscription ID found.")

        stripe.Subscription.modify(
            sub.provider_subscription_id,
            cancel_at_period_end=True
        )
        self.sub_repo.update(sub, {"cancel_at_period_end": True})
        self.db.refresh(sub)
        return sub

    # ─── Razorpay ──────────────────────────────────────────────────────────

    def create_razorpay_order(self, company_id: uuid.UUID, data: RazorpayCheckoutRequest) -> CheckoutSessionResponse:
        """Creates a Razorpay subscription order."""
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise HTTPException(status_code=503, detail="Razorpay is not configured.")
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        company = self.company_repo.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")

        plan = self.plan_repo.get_by_id(data.plan_id)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=404, detail="Plan not found or inactive.")

        # Create Razorpay order
        order_data = {
            "amount": int(float(plan.amount) * 100),
            "currency": plan.currency.upper(),
            "payment_capture": 1,
            "notes": {
                "company_id": str(company_id),
                "plan_id": str(plan.id),
                "customer_name": data.customer_name,
                "customer_email": data.customer_email,
            }
        }
        order = client.order.create(data=order_data)

        # Create pending subscription record
        existing = self.sub_repo.get_active_by_company(company_id)
        if existing:
            sub = existing
        else:
            sub = self.sub_repo.create({
                "company_id": company_id,
                "plan_id": plan.id,
                "provider": SubscriptionProvider.RAZORPAY,
                "status": SubscriptionStatus.INCOMPLETE,
                "payment_id": order["id"],
                "metadata_": {
                    "razorpay_order_id": order["id"],
                    "customer_name": data.customer_name,
                    "customer_email": data.customer_email,
                }
            })

        return CheckoutSessionResponse(
            order_id=order["id"],
            subscription_id=sub.id,
            provider="razorpay"
        )

    def verify_razorpay_payment(
        self,
        company_id: uuid.UUID,
        data: RazorpayVerifyRequest
    ) -> SubscriptionResponse:
        """Verifies Razorpay signature and activates the subscription."""
        import hmac
        import hashlib

        if not settings.RAZORPAY_KEY_SECRET:
            raise HTTPException(status_code=503, detail="Razorpay is not configured.")

        # Signature verification
        msg = f"{data.razorpay_order_id}|{data.razorpay_payment_id}"
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, data.razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid Razorpay signature. Payment verification failed.")

        plan = self.plan_repo.get_by_id(data.plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found.")

        # Find or create subscription
        sub = self.sub_repo.get_active_by_company(company_id)
        if not sub:
            sub = self.sub_repo.create({
                "company_id": company_id,
                "plan_id": plan.id,
                "provider": SubscriptionProvider.RAZORPAY,
                "payment_id": data.razorpay_payment_id,
                "status": SubscriptionStatus.ACTIVE,
            })
        else:
            self.sub_repo.update(sub, {
                "status": SubscriptionStatus.ACTIVE,
                "payment_id": data.razorpay_payment_id,
            })

        # Create invoice record
        invoice = self.invoice_repo.create({
            "company_id": company_id,
            "subscription_id": sub.id,
            "provider": "razorpay",
            "provider_payment_id": data.razorpay_payment_id,
            "amount_due": float(plan.amount),
            "amount_paid": float(plan.amount),
            "currency": plan.currency,
            "status": InvoiceStatus.PAID,
            "paid_at": datetime.now(timezone.utc),
        })

        # Update subscription with invoice ref
        self.sub_repo.update(sub, {"invoice_id": invoice.id})

        # Update company plan and status
        self._activate_company_plan(company_id, plan)

        self.db.refresh(sub)
        return sub

    # ─── Shared helpers ─────────────────────────────────────────────────────

    def _activate_company_plan(self, company_id: uuid.UUID, plan) -> None:
        """Updates company plan, status, limits, and AI credits after successful payment."""
        company = self.company_repo.get_by_id(company_id)
        if not company:
            return
        plan_enum = PLAN_NAME_MAP.get(plan.name.lower(), CompanyPlan.STARTER)
        company.plan = plan_enum
        company.status = CompanyStatus.ACTIVE
        company.max_users = plan.max_users
        company.max_apps = plan.max_apps
        # Top up AI credits
        from decimal import Decimal
        company.credits_balance = (company.credits_balance or Decimal("0")) + Decimal(str(plan.ai_credits))
        self.db.commit()

        # Sync usage meter limits immediately (Task 29)
        try:
            from app.usage.service import UsageService
            UsageService(self.db).apply_plan_limits(
                company_id,
                plan.name,
                plan_row=plan,
                emit_upgraded=True,
            )
        except Exception as e:
            logger.error(f"Failed to apply usage plan limits: {e}")

    def handle_stripe_subscription_event(self, stripe_sub_data: dict, event_type: str) -> None:
        """Called by the Stripe webhook handler to sync subscription state."""
        stripe_sub_id = stripe_sub_data.get("id")
        if not stripe_sub_id:
            return

        sub = self.sub_repo.get_by_provider_subscription_id(stripe_sub_id)
        # Try to get company_id from metadata
        meta = stripe_sub_data.get("metadata", {})
        company_id_str = meta.get("company_id")
        plan_id_str = meta.get("plan_id")

        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "trialing": SubscriptionStatus.TRIALING,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELLED,
            "unpaid": SubscriptionStatus.UNPAID,
            "incomplete": SubscriptionStatus.INCOMPLETE,
        }

        stripe_status = stripe_sub_data.get("status", "incomplete")
        new_status = status_map.get(stripe_status, SubscriptionStatus.INCOMPLETE)

        period_start = datetime.fromtimestamp(stripe_sub_data["current_period_start"], tz=timezone.utc) if stripe_sub_data.get("current_period_start") else None
        period_end   = datetime.fromtimestamp(stripe_sub_data["current_period_end"], tz=timezone.utc)   if stripe_sub_data.get("current_period_end")   else None
        trial_end    = datetime.fromtimestamp(stripe_sub_data["trial_end"], tz=timezone.utc)            if stripe_sub_data.get("trial_end")            else None

        update_data = {
            "status": new_status,
            "provider_subscription_id": stripe_sub_id,
            "cancel_at_period_end": stripe_sub_data.get("cancel_at_period_end", False),
            "current_period_start": period_start,
            "current_period_end": period_end,
            "trial_end": trial_end,
        }

        if sub:
            self.sub_repo.update(sub, update_data)
        elif company_id_str:
            # Create subscription record if it doesn't exist yet
            try:
                company_id = uuid.UUID(company_id_str)
                plan_id = uuid.UUID(plan_id_str) if plan_id_str else None
                customer_id = stripe_sub_data.get("customer")
                create_data = {
                    "company_id": company_id,
                    "plan_id": plan_id,
                    "provider": SubscriptionProvider.STRIPE,
                    "provider_customer_id": customer_id,
                    **update_data
                }
                sub = self.sub_repo.create(create_data)
            except Exception as e:
                logger.error(f"Failed to create subscription from webhook: {e}")
                return

        # Activate company if subscription is now active
        if new_status == SubscriptionStatus.ACTIVE and company_id_str and plan_id_str:
            try:
                cid = uuid.UUID(company_id_str)
                pid = uuid.UUID(plan_id_str)
                plan = self.plan_repo.get_by_id(pid)
                if plan:
                    self._activate_company_plan(cid, plan)
            except Exception as e:
                logger.error(f"Failed to activate company plan from webhook: {e}")

        # If cancelled, revert company to FREE + downgrade usage limits
        if new_status == SubscriptionStatus.CANCELLED and company_id_str:
            try:
                cid = uuid.UUID(company_id_str)
                company = self.company_repo.get_by_id(cid)
                if company:
                    company.plan = CompanyPlan.FREE
                    company.status = CompanyStatus.ACTIVE
                    company.max_users = 5
                    company.max_apps = 1
                    self.db.commit()
                    from app.usage.service import UsageService
                    UsageService(self.db).downgrade_to_free(cid)
            except Exception as e:
                logger.error(f"Failed to revert company plan after cancellation: {e}")
