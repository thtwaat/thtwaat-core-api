"""
app/payments/subscriptions/service.py

Orchestrates subscription lifecycle for both Stripe and Razorpay.
"""
import uuid
import logging
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

import stripe

from app.config.settings import settings
from app.payments.plans.repository import PlanRepository
from app.payments.subscriptions.model import Subscription, SubscriptionStatus, SubscriptionProvider
from app.payments.subscriptions.schema import (
    StripeCheckoutRequest, RazorpayCheckoutRequest, RazorpayVerifyRequest,
    RazorpaySubscriptionCheckoutRequest, RazorpaySubscriptionVerifyRequest,
    CheckoutSessionResponse, SubscriptionResponse, ChangePlanRequest
)
from app.payments.providers.razorpay import extract_subscription_period
from app.payments.subscriptions.repository import SubscriptionRepository
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.invoices.repository import InvoiceRepository
from app.companies.repository import CompanyRepository
from app.companies.model import Company, CompanyPlan, CompanyStatus
from app.payments.provider_flags import stripe_enabled, razorpay_enabled
from app.payments.billing_extras import (
    apply_coupon_discount,
    get_active_coupon,
)
from app.payments.region_pricing import (
    plan_currency_for_region,
    plan_price_for_region,
)
from app.payments.billing_region import resolve_region_for_company

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

    def create_stripe_checkout_session(
        self,
        company_id: uuid.UUID,
        data: StripeCheckoutRequest,
        *,
        request=None,
    ) -> CheckoutSessionResponse:
        """Creates a Stripe Checkout Session for a plan subscription."""
        from decimal import Decimal

        company = self.company_repo.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")

        plan = self.plan_repo.get_by_id(data.plan_id)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=404, detail="Plan not found or inactive.")

        if getattr(plan, "is_custom_pricing", False):
            raise HTTPException(
                status_code=400,
                detail="Enterprise plan uses custom pricing. Contact sales.",
            )

        region = resolve_region_for_company(
            self.db, company_id, request, country=getattr(data, "country", None)
        )
        # India selection should use Razorpay/INR checkout, not Stripe.
        if region.region == "IN" and razorpay_enabled():
            raise HTTPException(
                status_code=400,
                detail="Indian billing uses Razorpay (INR). Use the Razorpay order flow.",
            )

        use_yearly = (data.interval or plan.interval or "month").lower() == "year"
        amount = plan_price_for_region(plan, region, interval="year" if use_yearly else "month")
        if amount <= 0:
            try:
                existing = self.sub_repo.get_active_by_company(company_id)
            except Exception as exc:
                logger.warning("free checkout: active-sub lookup failed: %s", exc)
                existing = None
            if not existing:
                try:
                    self.sub_repo.create(
                        {
                            "company_id": company_id,
                            "plan_id": plan.id,
                            "provider": SubscriptionProvider.MANUAL.value,
                            "status": SubscriptionStatus.ACTIVE.value,
                            "metadata_": {"source": "free_plan_checkout"},
                        }
                    )
                except Exception as exc:
                    # Already on free / duplicate - still activate limits and succeed.
                    logger.warning("free checkout: sub create skipped: %s", exc)
                    self.db.rollback()
            try:
                self._activate_company_plan(company_id, plan)
            except Exception as exc:
                logger.warning("free checkout: activate plan failed: %s", exc)
                self.db.rollback()
            return CheckoutSessionResponse(
                checkout_url=data.success_url,
                provider="manual",
            )

        if not stripe_enabled():
            raise HTTPException(status_code=503, detail="Stripe billing is not enabled or configured.")
        stripe.api_key = settings.STRIPE_SECRET_KEY

        price_id = plan.stripe_yearly_price_id if use_yearly else plan.stripe_price_id
        if not price_id:
            raise HTTPException(
                status_code=400,
                detail=f"Plan '{plan.name}' does not have a Stripe price configured. Ask admin to set stripe_price_id.",
            )

        customer_id = self._get_or_create_stripe_customer(company)

        session_kwargs = {
            "customer": customer_id,
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": data.success_url,
            "cancel_url": data.cancel_url,
            "metadata": {
                "company_id": str(company_id),
                "plan_id": str(plan.id),
                "billing_region": region.region,
                "billing_currency": "USD",
            },
            "subscription_data": {
                "metadata": {
                    "company_id": str(company_id),
                    "plan_id": str(plan.id),
                    "billing_region": region.region,
                }
            },
        }
        trial_days = data.trial_days
        if trial_days is None:
            trial_days = int(getattr(plan, "trial_days", 0) or 0)
        if trial_days and trial_days > 0:
            session_kwargs["subscription_data"]["trial_period_days"] = int(trial_days)

        if data.coupon_code:
            coupon = get_active_coupon(self.db, data.coupon_code)
            if not coupon:
                raise HTTPException(status_code=400, detail="Invalid coupon code")
            if coupon.stripe_coupon_id:
                session_kwargs["discounts"] = [{"coupon": coupon.stripe_coupon_id}]
            session_kwargs["metadata"]["coupon_code"] = coupon.code

        session = stripe.checkout.Session.create(**session_kwargs)

        # Create a pending subscription record
        existing = self.sub_repo.get_active_by_company(company_id)
        if not existing:
            self.sub_repo.create({
                "company_id": company_id,
                "plan_id": plan.id,
                "provider": SubscriptionProvider.STRIPE,
                "provider_customer_id": customer_id,
                "status": SubscriptionStatus.INCOMPLETE,
                "metadata_": {"checkout_session_id": session.id, "billing_region": region.region}
            })

        return CheckoutSessionResponse(checkout_url=session.url, provider="stripe")

    def get_subscription(self, company_id: uuid.UUID) -> Optional[Subscription]:
        """Returns the active subscription for a company."""
        return self.sub_repo.get_active_by_company(company_id)

    def list_subscriptions(self, company_id: uuid.UUID) -> List[Subscription]:
        return self.sub_repo.list_by_company(company_id)

    def cancel_stripe_subscription(self, company_id: uuid.UUID) -> SubscriptionResponse:
        """Cancels an active subscription at period end (Stripe or Razorpay)."""
        return self.cancel_subscription(company_id)

    def cancel_subscription(self, company_id: uuid.UUID) -> SubscriptionResponse:
        sub = self.sub_repo.get_active_by_company(company_id)
        if not sub:
            raise HTTPException(status_code=404, detail="No active subscription found.")

        if sub.provider == SubscriptionProvider.STRIPE:
            if not stripe_enabled():
                raise HTTPException(status_code=503, detail="Stripe billing is not enabled or configured.")
            stripe.api_key = settings.STRIPE_SECRET_KEY
            if not sub.provider_subscription_id:
                raise HTTPException(status_code=400, detail="No Stripe subscription ID found.")
            stripe.Subscription.modify(
                sub.provider_subscription_id,
                cancel_at_period_end=True,
            )
            self.sub_repo.update(sub, {"cancel_at_period_end": True})
        elif sub.provider == SubscriptionProvider.RAZORPAY:
            if not razorpay_enabled():
                raise HTTPException(status_code=503, detail="Razorpay billing is not enabled or configured.")
            if sub.provider_subscription_id:
                import razorpay

                client = razorpay.Client(
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                )
                try:
                    # cancel_at_cycle_end=1 schedules the cancellation for the
                    # end of the current billing cycle instead of cancelling
                    # (and revoking the mandate) immediately. Local status
                    # stays ACTIVE/cancel_at_period_end=True until Razorpay's
                    # subscription.cancelled webhook confirms it actually
                    # ended — mirrors the Stripe branch above, which also
                    # only flips a flag here and lets the webhook finalize.
                    client.subscription.cancel(
                        sub.provider_subscription_id, {"cancel_at_cycle_end": 1}
                    )
                except Exception as exc:
                    logger.warning("razorpay cancel remote failed: %s", exc)
            else:
                # Legacy one-time Razorpay "subscription" (no real provider
                # subscription — see docs/billing/razorpay-recurring.md).
                # There is nothing recurring to cancel on Razorpay's side;
                # cancelling locally just stops it from being billed again
                # under this row (it was never going to auto-renew anyway).
                logger.info(
                    "razorpay cancel: sub=%s has no provider_subscription_id (legacy one-time order)",
                    sub.id,
                )
            self.sub_repo.update(sub, {"cancel_at_period_end": True})
        else:
            # Manual / free
            self.sub_repo.update(
                sub,
                {
                    "status": SubscriptionStatus.CANCELLED,
                    "cancel_at_period_end": False,
                    "cancelled_at": datetime.now(timezone.utc),
                },
            )
            self._downgrade_to_free(company_id)

        self.db.refresh(sub)
        return sub

    def resume_subscription(self, company_id: uuid.UUID) -> SubscriptionResponse:
        """Undo cancel-at-period-end when still within the paid period."""
        sub = self.sub_repo.get_active_by_company(company_id)
        if not sub:
            raise HTTPException(status_code=404, detail="No active subscription found.")
        if not sub.cancel_at_period_end:
            raise HTTPException(status_code=400, detail="Subscription is not pending cancellation.")

        if sub.provider == SubscriptionProvider.STRIPE:
            if not stripe_enabled():
                raise HTTPException(status_code=503, detail="Stripe billing is not enabled or configured.")
            stripe.api_key = settings.STRIPE_SECRET_KEY
            if not sub.provider_subscription_id:
                raise HTTPException(status_code=400, detail="No Stripe subscription ID found.")
            stripe.Subscription.modify(
                sub.provider_subscription_id,
                cancel_at_period_end=False,
            )
        elif sub.provider == SubscriptionProvider.RAZORPAY and sub.provider_subscription_id:
            # The installed Razorpay SDK (razorpay.resources.subscription)
            # exposes create/cancel/pause/resume/edit/cancel_scheduled_changes
            # but no documented way to reverse a cancel_at_cycle_end request
            # once Razorpay has accepted it. Flipping our local flag back
            # without an equivalent remote change would desync local state
            # from what Razorpay will actually do at cycle end — refuse
            # instead of guessing at an unconfirmed API call.
            raise HTTPException(
                status_code=400,
                detail=(
                    "This Razorpay subscription is scheduled to cancel at the end of "
                    "the current billing cycle and cannot be resumed via the API. "
                    "Let it lapse and re-subscribe, or contact support."
                ),
            )
        self.sub_repo.update(sub, {"cancel_at_period_end": False, "cancelled_at": None})
        self.db.refresh(sub)
        return sub

    def change_plan(
        self, company_id: uuid.UUID, data: ChangePlanRequest, *, request=None
    ) -> CheckoutSessionResponse:
        """
        Upgrade/downgrade via checkout for paid providers, or immediate activate for free.
        Region selects provider: India → Razorpay/INR, International → Stripe/USD.
        """
        plan = self.plan_repo.get_by_id(data.plan_id)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=404, detail="Plan not found or inactive.")

        if getattr(plan, "is_custom_pricing", False):
            raise HTTPException(
                status_code=400,
                detail="Enterprise plan uses custom pricing. Contact sales.",
            )

        region = resolve_region_for_company(
            self.db, company_id, request, country=getattr(data, "country", None)
        )
        use_yearly = (data.interval or plan.interval or "month").lower() == "year"
        amount = float(plan_price_for_region(plan, region, interval="year" if use_yearly else "month"))
        if amount <= 0:
            existing = self.sub_repo.get_active_by_company(company_id)
            if existing:
                self.sub_repo.update(
                    existing,
                    {
                        "plan_id": plan.id,
                        "status": SubscriptionStatus.ACTIVE,
                        "cancel_at_period_end": False,
                    },
                )
            else:
                self.sub_repo.create(
                    {
                        "company_id": company_id,
                        "plan_id": plan.id,
                        "provider": SubscriptionProvider.MANUAL,
                        "status": SubscriptionStatus.ACTIVE,
                        "metadata_": {"source": "change_plan_free"},
                    }
                )
            self._activate_company_plan(company_id, plan)
            return CheckoutSessionResponse(checkout_url=None, provider="manual")

        # Paid: route by selected country / region
        success = data.success_url or "https://app.thtwaat.com/app/billing?upgraded=1"
        cancel = data.cancel_url or "https://app.thtwaat.com/app/billing?cancelled=1"
        if region.region == "IN":
            if not razorpay_enabled():
                raise HTTPException(
                    status_code=503,
                    detail="Razorpay is required for Indian (INR) billing but is not configured.",
                )
            raise HTTPException(
                status_code=400,
                detail="Use Razorpay order+verify flow for Indian plan changes.",
            )
        if stripe_enabled():
            return self.create_stripe_checkout_session(
                company_id,
                StripeCheckoutRequest(
                    plan_id=data.plan_id,
                    success_url=success,
                    cancel_url=cancel,
                    coupon_code=data.coupon_code,
                    interval=data.interval,
                    country=getattr(data, "country", None),
                ),
                request=request,
            )
        if razorpay_enabled():
            raise HTTPException(
                status_code=400,
                detail="Use Razorpay order+verify flow for plan changes when Stripe is disabled.",
            )
        raise HTTPException(status_code=503, detail="No billing provider enabled.")

    def _downgrade_to_free(self, company_id: uuid.UUID) -> None:
        company = self.company_repo.get_by_id(company_id)
        if not company:
            return
        company.plan = CompanyPlan.FREE
        company.status = CompanyStatus.ACTIVE
        company.max_users = 5
        company.max_apps = 1
        self.db.commit()
        try:
            from app.usage.service import UsageService

            UsageService(self.db).apply_plan_limits(company_id, "free")
        except Exception as exc:
            logger.warning("downgrade usage limits failed: %s", exc)

    # ─── Razorpay ──────────────────────────────────────────────────────────

    def create_razorpay_order(
        self, company_id: uuid.UUID, data: RazorpayCheckoutRequest, *, request=None
    ) -> CheckoutSessionResponse:
        """Creates a Razorpay subscription order (INR for India region)."""
        if not razorpay_enabled():
            raise HTTPException(status_code=503, detail="Razorpay billing is not enabled or configured.")
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        company = self.company_repo.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")

        plan = self.plan_repo.get_by_id(data.plan_id)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=404, detail="Plan not found or inactive.")

        if getattr(plan, "is_custom_pricing", False):
            raise HTTPException(
                status_code=400,
                detail="Enterprise plan uses custom pricing. Contact sales.",
            )

        region = resolve_region_for_company(
            self.db, company_id, request, country=getattr(data, "country", None)
        )
        # Razorpay is India/INR; charge INR catalog even if called with a non-IN override.
        billing_region = region
        if region.region != "IN":
            from app.payments.region_pricing import BillingRegion

            billing_region = BillingRegion(
                "IN", "INR", "razorpay", region.country_code or "IN", "razorpay_checkout"
            )

        use_yearly = (data.interval or plan.interval or "month").lower() == "year"
        amount_dec = plan_price_for_region(
            plan, billing_region, interval="year" if use_yearly else "month"
        )
        currency = plan_currency_for_region(plan, billing_region)
        coupon_code = None
        if data.coupon_code:
            coupon = get_active_coupon(self.db, data.coupon_code)
            if not coupon:
                raise HTTPException(status_code=400, detail="Invalid coupon code")
            amount_dec = apply_coupon_discount(amount_dec, coupon)
            coupon_code = coupon.code
            coupon.redeemed_count = int(coupon.redeemed_count or 0) + 1
            self.db.commit()

        if amount_dec <= 0:
            raise HTTPException(status_code=400, detail="Plan amount must be greater than zero for Razorpay.")

        # Create Razorpay order (amount in smallest currency unit)
        order_data = {
            "amount": int(float(amount_dec) * 100),
            "currency": currency.upper(),
            "payment_capture": 1,
            "notes": {
                "company_id": str(company_id),
                "plan_id": str(plan.id),
                "customer_name": data.customer_name,
                "customer_email": data.customer_email,
                "billing_region": billing_region.region,
                "billing_currency": currency.upper(),
                **({"coupon_code": coupon_code} if coupon_code else {}),
            },
        }
        order = client.order.create(data=order_data)

        order_meta = {
            "razorpay_order_id": order["id"],
            "plan_id": str(plan.id),
            "customer_name": data.customer_name,
            "customer_email": data.customer_email,
        }

        # Persist server-side order → plan mapping (never rely on client at verify time).
        existing = self.sub_repo.get_active_by_company(company_id)
        if existing:
            meta = dict(existing.metadata_ or {})
            meta.update(order_meta)
            meta["pending_plan_id"] = str(plan.id)
            sub = self.sub_repo.update(existing, {
                "payment_id": order["id"],
                "metadata_": meta,
            })
        else:
            pending = self.sub_repo.get_incomplete_by_company(
                company_id, SubscriptionProvider.RAZORPAY
            )
            if pending:
                meta = dict(pending.metadata_ or {})
                meta.update(order_meta)
                sub = self.sub_repo.update(pending, {
                    "plan_id": plan.id,
                    "payment_id": order["id"],
                    "metadata_": meta,
                    "status": SubscriptionStatus.INCOMPLETE,
                })
            else:
                sub = self.sub_repo.create({
                    "company_id": company_id,
                    "plan_id": plan.id,
                    "provider": SubscriptionProvider.RAZORPAY,
                    "status": SubscriptionStatus.INCOMPLETE,
                    "payment_id": order["id"],
                    "metadata_": order_meta,
                })

        return CheckoutSessionResponse(
            order_id=order["id"],
            subscription_id=sub.id,
            provider="razorpay"
        )

    def _resolve_razorpay_order_subscription(
        self,
        company_id: uuid.UUID,
        razorpay_order_id: str,
    ) -> Optional[Subscription]:
        """Locate the pending/active subscription bound to this Razorpay order."""
        sub = self.sub_repo.get_by_payment_id(razorpay_order_id)
        if sub and sub.company_id == company_id:
            return sub
        # After a prior verify, payment_id may already be the payment id; use metadata.
        for candidate in self.sub_repo.list_by_company(company_id):
            meta = candidate.metadata_ or {}
            if meta.get("razorpay_order_id") == razorpay_order_id:
                return candidate
        return None

    def _trusted_plan_id_from_subscription(self, sub: Subscription) -> uuid.UUID:
        """Plan must come from the server-side order mapping, never the client body."""
        meta = sub.metadata_ or {}
        for key in ("pending_plan_id", "plan_id"):
            raw = meta.get(key)
            if raw:
                try:
                    return uuid.UUID(str(raw))
                except (TypeError, ValueError):
                    continue
        return sub.plan_id

    def verify_razorpay_payment(
        self,
        company_id: uuid.UUID,
        data: RazorpayVerifyRequest
    ) -> SubscriptionResponse:
        """Verifies Razorpay signature and activates the subscription.

        Plan activation uses the server-side order mapping only. Client ``plan_id``
        is accepted for backward compatibility but must match the stored plan.
        """
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

        # Idempotent re-verify: same payment already recorded.
        existing_invoice = self.invoice_repo.get_by_provider_payment_id(data.razorpay_payment_id)
        if existing_invoice and existing_invoice.company_id == company_id:
            if existing_invoice.subscription_id:
                sub = self.sub_repo.get_by_id(existing_invoice.subscription_id)
                if sub and sub.company_id == company_id:
                    return sub
            active = self.sub_repo.get_active_by_company(company_id)
            if active:
                return active
            raise HTTPException(
                status_code=400,
                detail="Payment already verified but subscription mapping is missing.",
            )

        sub = self._resolve_razorpay_order_subscription(company_id, data.razorpay_order_id)
        if not sub:
            raise HTTPException(
                status_code=400,
                detail="No server-side order mapping found for this Razorpay order.",
            )

        trusted_plan_id = self._trusted_plan_id_from_subscription(sub)
        if data.plan_id != trusted_plan_id:
            raise HTTPException(
                status_code=400,
                detail="Submitted plan_id does not match the plan bound to this order.",
            )

        plan = self.plan_repo.get_by_id(trusted_plan_id)
        if not plan:
            raise HTTPException(status_code=400, detail="Plan bound to this order was not found.")

        self.sub_repo.update(sub, {
            "plan_id": trusted_plan_id,
            "status": SubscriptionStatus.ACTIVE,
            "payment_id": data.razorpay_payment_id,
        })

        # Create invoice record — idempotent by provider_payment_id (DB-enforced
        # via a unique index, not just this pre-check) so this is safe even if
        # the payment.captured webhook for the same payment races this call.
        invoice, created = self.invoice_repo.create_idempotent_by_payment_id({
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

        # Update company plan/status/limits and grant AI credits — but only
        # the first time this payment's invoice is actually created. If the
        # payment.captured webhook already created it (raced ahead of this
        # call), activation already happened there; doing it again here would
        # double-grant credits for the same payment.
        if created:
            self._activate_company_plan(company_id, plan)

        self.db.refresh(sub)
        return sub

    # ─── Razorpay recurring Subscriptions (real recurring billing) ─────────
    #
    # create_razorpay_order/verify_razorpay_payment above remain a one-time
    # Order+verify flow and are left untouched for any non-recurring caller.
    # The methods below use the Razorpay *Subscription* API so a plan can
    # actually auto-renew. See docs/billing/razorpay-recurring.md.

    def _ensure_razorpay_plan(self, client, plan, use_yearly: bool, billing_region) -> str:
        """Resolve (creating if necessary) the Razorpay Plan id for this
        Plan/interval. Never creates a duplicate Razorpay Plan once an id is
        already recorded. Amount/currency/interval always come from the
        server-side Plan row — the caller never supplies price or interval
        for plan creation.
        """
        field = "razorpay_yearly_plan_id" if use_yearly else "razorpay_plan_id"
        self.db.refresh(plan)
        existing = getattr(plan, field, None)
        if existing:
            return existing

        amount_dec = plan_price_for_region(
            plan, billing_region, interval="year" if use_yearly else "month"
        )
        if amount_dec <= 0:
            raise HTTPException(
                status_code=400,
                detail="Plan amount must be greater than zero for a Razorpay recurring subscription.",
            )
        currency = plan_currency_for_region(plan, billing_region)

        razorpay_plan = client.plan.create(data={
            "period": "yearly" if use_yearly else "monthly",
            "interval": int(plan.interval_count or 1),
            "item": {
                "name": f"{plan.name} ({'Yearly' if use_yearly else 'Monthly'})",
                "amount": int(float(amount_dec) * 100),
                "currency": currency.upper(),
                "description": plan.description or plan.name,
            },
            "notes": {"plan_id": str(plan.id), "interval": "year" if use_yearly else "month"},
        })
        razorpay_plan_id = razorpay_plan["id"]

        # Re-check right before writing: a concurrent request may have
        # created and persisted one while this call was talking to Razorpay.
        # Keep whichever id landed first rather than overwriting it —
        # Razorpay has no delete-plan API, so a rare duplicate Plan object on
        # their side is harmless; an orphaned reference in our own DB is not.
        self.db.refresh(plan)
        winner = getattr(plan, field, None)
        if winner:
            return winner
        self.plan_repo.update(plan, {field: razorpay_plan_id})
        return razorpay_plan_id

    def create_razorpay_subscription(
        self,
        company_id: uuid.UUID,
        data: RazorpaySubscriptionCheckoutRequest,
        *,
        request=None,
    ) -> CheckoutSessionResponse:
        """Creates a real, recurring Razorpay Subscription (not an Order)."""
        if not razorpay_enabled():
            raise HTTPException(status_code=503, detail="Razorpay billing is not enabled or configured.")
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        company = self.company_repo.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")

        plan = self.plan_repo.get_by_id(data.plan_id)
        if not plan or not plan.is_active:
            raise HTTPException(status_code=404, detail="Plan not found or inactive.")
        if getattr(plan, "is_custom_pricing", False):
            raise HTTPException(
                status_code=400,
                detail="Enterprise plan uses custom pricing. Contact sales.",
            )

        # Never create a second live Razorpay Subscription (mandate) while an
        # existing one is already active — that would orphan the original
        # (still auto-charging on Razorpay's side, but no longer tracked
        # locally once its provider_subscription_id is overwritten below).
        # A row with no provider_subscription_id is either a legacy one-time
        # Order-flow row or a not-yet-authorized INCOMPLETE attempt — neither
        # has a live mandate, so it is safe to proceed/reuse (see the reuse
        # branch further down).
        existing = self.sub_repo.get_active_by_company(company_id)
        if existing and existing.provider == SubscriptionProvider.RAZORPAY and existing.provider_subscription_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "An active Razorpay recurring subscription already exists for this "
                    "company. Cancel it before starting a new one."
                ),
            )

        region = resolve_region_for_company(
            self.db, company_id, request, country=getattr(data, "country", None)
        )
        # Razorpay recurring billing is INR/India-only in this codebase,
        # same constraint as the one-time order flow above.
        billing_region = region
        if region.region != "IN":
            from app.payments.region_pricing import BillingRegion

            billing_region = BillingRegion(
                "IN", "INR", "razorpay", region.country_code or "IN", "razorpay_subscription_checkout"
            )

        use_yearly = (data.interval or plan.interval or "month").lower() == "year"
        razorpay_plan_id = self._ensure_razorpay_plan(client, plan, use_yearly, billing_region)

        total_count = (
            int(getattr(settings, "RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_YEARLY", 15) or 15)
            if use_yearly
            else int(getattr(settings, "RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_MONTHLY", 120) or 120)
        )

        razorpay_sub = client.subscription.create(data={
            "plan_id": razorpay_plan_id,
            "total_count": total_count,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "company_id": str(company_id),
                "plan_id": str(plan.id),
                "customer_name": data.customer_name,
                "customer_email": data.customer_email,
                "billing_region": billing_region.region,
                "interval": "year" if use_yearly else "month",
            },
        })
        razorpay_sub_id = razorpay_sub["id"]

        sub_meta = {
            "pending_plan_id": str(plan.id),
            "razorpay_plan_id": razorpay_plan_id,
            "customer_name": data.customer_name,
            "customer_email": data.customer_email,
            "interval": "year" if use_yearly else "month",
        }

        # Only reuse an existing row that is already a Razorpay subscription
        # attempt — never overwrite an active Stripe/manual subscription's
        # row with Razorpay identifiers. (The conflict guard above already
        # ruled out `existing` being a live recurring Razorpay mandate.)
        if existing and existing.provider == SubscriptionProvider.RAZORPAY:
            meta = dict(existing.metadata_ or {})
            meta.update(sub_meta)
            sub = self.sub_repo.update(existing, {
                "provider_subscription_id": razorpay_sub_id,
                "plan_id": plan.id,
                "status": SubscriptionStatus.INCOMPLETE,
                "metadata_": meta,
            })
        else:
            pending = self.sub_repo.get_incomplete_by_company(
                company_id, SubscriptionProvider.RAZORPAY
            )
            if pending:
                meta = dict(pending.metadata_ or {})
                meta.update(sub_meta)
                sub = self.sub_repo.update(pending, {
                    "plan_id": plan.id,
                    "provider_subscription_id": razorpay_sub_id,
                    "metadata_": meta,
                    "status": SubscriptionStatus.INCOMPLETE,
                })
            else:
                sub = self.sub_repo.create({
                    "company_id": company_id,
                    "plan_id": plan.id,
                    "provider": SubscriptionProvider.RAZORPAY,
                    "provider_subscription_id": razorpay_sub_id,
                    "status": SubscriptionStatus.INCOMPLETE,
                    "metadata_": sub_meta,
                })

        return CheckoutSessionResponse(
            razorpay_subscription_id=razorpay_sub_id,
            subscription_id=sub.id,
            provider="razorpay",
        )

    def verify_razorpay_subscription_payment(
        self,
        company_id: uuid.UUID,
        data: RazorpaySubscriptionVerifyRequest,
    ) -> SubscriptionResponse:
        """Verifies the first-charge signature for a Razorpay Subscription.

        Signature verification proves the (payment_id, subscription_id) pair
        is genuine, but it does NOT activate the subscription, populate the
        billing period, or write an invoice — that happens only in the
        subscription.charged/subscription.activated webhook handlers, which
        carry the real current_start/current_end and are delivered
        regardless of whether the customer's browser survives the checkout
        redirect. This call is intentionally a no-op beyond verification and
        an idempotent bookkeeping note.
        """
        if not settings.RAZORPAY_KEY_SECRET:
            raise HTTPException(status_code=503, detail="Razorpay is not configured.")

        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            client.utility.verify_subscription_payment_signature({
                "razorpay_subscription_id": data.razorpay_subscription_id,
                "razorpay_payment_id": data.razorpay_payment_id,
                "razorpay_signature": data.razorpay_signature,
            })
        except razorpay.errors.SignatureVerificationError:
            raise HTTPException(
                status_code=400,
                detail="Invalid Razorpay signature. Payment verification failed.",
            )

        sub = self.sub_repo.get_by_provider_subscription_id(data.razorpay_subscription_id)
        if not sub or sub.company_id != company_id:
            raise HTTPException(
                status_code=400,
                detail="No subscription found for this Razorpay subscription id.",
            )

        trusted_plan_id = self._trusted_plan_id_from_subscription(sub)
        if data.plan_id != trusted_plan_id:
            raise HTTPException(
                status_code=400,
                detail="Submitted plan_id does not match the plan bound to this subscription.",
            )

        if sub.status != SubscriptionStatus.ACTIVE:
            meta = dict(sub.metadata_ or {})
            meta["first_charge_verified_payment_id"] = data.razorpay_payment_id
            sub = self.sub_repo.update(sub, {"metadata_": meta})

        return sub

    def reconcile_razorpay_subscriptions(self, *, grace_hours: int = 24) -> dict:
        """Safety net for dropped/delayed Razorpay webhooks.

        Finds real Razorpay subscriptions (``provider_subscription_id`` set —
        legacy one-time Razorpay rows never have one and are never touched
        here, see docs/billing/razorpay-recurring.md) whose local
        ``current_period_end`` lapsed more than ``grace_hours`` ago with no
        follow-up webhook, re-checks the *actual* status with Razorpay
        directly (never assumes non-payment from a missing webhook alone),
        and resyncs local state from that authoritative answer.
        """
        if not razorpay_enabled():
            return {"checked": 0, "flagged": 0, "skipped": "razorpay_disabled"}

        cutoff = datetime.now(timezone.utc) - timedelta(hours=grace_hours)
        stale = list(self.db.execute(
            select(Subscription).where(
                Subscription.provider == SubscriptionProvider.RAZORPAY,
                Subscription.provider_subscription_id.isnot(None),
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE.value,
                    SubscriptionStatus.PAST_DUE.value,
                ]),
                Subscription.current_period_end.isnot(None),
                Subscription.current_period_end < cutoff,
            )
        ).scalars().all())

        if not stale:
            return {"checked": 0, "flagged": 0}

        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        flagged = 0
        for sub in stale:
            try:
                remote = client.subscription.fetch(sub.provider_subscription_id)
            except Exception as exc:
                logger.warning("reconcile_razorpay: fetch failed sub=%s err=%s", sub.id, exc)
                continue

            remote_status = remote.get("status")
            if remote_status == "active":
                start, end = extract_subscription_period(remote)
                update = {"status": SubscriptionStatus.ACTIVE}
                if start:
                    update["current_period_start"] = start
                if end:
                    update["current_period_end"] = end
                self.sub_repo.update(sub, update)
            elif remote_status == "pending":
                self.sub_repo.update(sub, {"status": SubscriptionStatus.PAST_DUE})
            elif remote_status in ("halted", "cancelled", "completed", "expired"):
                self.sub_repo.update(
                    sub,
                    {
                        "status": (
                            SubscriptionStatus.UNPAID
                            if remote_status == "halted"
                            else SubscriptionStatus.CANCELLED
                        ),
                        "cancelled_at": datetime.now(timezone.utc),
                    },
                )
                self._downgrade_to_free(sub.company_id)
                flagged += 1
            else:
                logger.warning(
                    "reconcile_razorpay: unrecognized remote status=%s sub=%s",
                    remote_status, sub.id,
                )

        return {"checked": len(stale), "flagged": flagged}

    # ─── Shared helpers ─────────────────────────────────────────────────────

    def _sync_company_plan_metadata(self, company_id: uuid.UUID, plan) -> None:
        """Updates company plan, status, and limits. Idempotent — safe to call
        on every webhook delivery/retry/reconcile pass for the same plan, since
        it only ever sets fields to their current-plan value and never
        accumulates anything. Deliberately excludes AI credits — see
        ``_grant_plan_credits``, which is NOT safe to call more than once per
        real charge.
        """
        company = self.company_repo.get_by_id(company_id)
        if not company:
            return
        plan_enum = PLAN_NAME_MAP.get(plan.name.lower(), CompanyPlan.STARTER)
        company.plan = plan_enum
        company.status = CompanyStatus.ACTIVE
        company.max_users = plan.max_users
        company.max_apps = plan.max_apps
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

    def _grant_plan_credits(self, company_id: uuid.UUID, plan) -> None:
        """Tops up AI credits for one real charge. NOT idempotent by itself —
        it additively increments ``credits_balance`` every time it is called,
        so a caller must guarantee this runs exactly once per payment (e.g.
        gated on having just newly created that payment's Invoice row via
        ``InvoiceRepository.create_idempotent_by_payment_id`` — see the
        Razorpay webhook handlers). Never call this more than once for the
        same charge/payment id.
        """
        company = self.company_repo.get_by_id(company_id)
        if not company:
            return
        from decimal import Decimal
        company.credits_balance = (company.credits_balance or Decimal("0")) + Decimal(str(plan.ai_credits))
        self.db.commit()

    def _activate_company_plan(self, company_id: uuid.UUID, plan) -> None:
        """Full activation: metadata sync + a one-time AI-credit grant.

        Used by flows where a single event represents both the entitlement
        change AND a real charge (Stripe subscription events, the legacy
        Razorpay one-time Order verify/webhook). Razorpay recurring
        subscriptions split status activation (``subscription.activated``)
        from the actual charge (``subscription.charged``) into two distinct
        webhook events — those callers must invoke
        ``_sync_company_plan_metadata``/``_grant_plan_credits`` directly
        instead of this method, or the credit grant would double-fire.
        """
        self._sync_company_plan_metadata(company_id, plan)
        self._grant_plan_credits(company_id, plan)

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
