"""
app/payments/webhooks/router.py

Webhook endpoints for Stripe and Razorpay.
NO JWT authentication — secured via signature verification.
"""
import json
import logging
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments/webhooks", tags=["Webhooks"])


@router.post(
    "/stripe",
    summary="Stripe webhook endpoint",
    description="Receives and processes Stripe webhook events. Verifies signature using STRIPE_WEBHOOK_SECRET."
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db)
):
    """Stripe webhook handler with signature verification."""
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhooks are not configured.")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header.")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError as e:
        logger.warning(f"[Stripe Webhook] Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature.")
    except Exception as e:
        logger.error(f"[Stripe Webhook] Failed to parse event: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload.")

    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info(f"[Stripe Webhook] Received event: {event_type}")

    from app.payments.subscriptions.service import SubscriptionService
    from app.payments.invoices.repository import InvoiceRepository
    from app.payments.invoices.model import InvoiceStatus
    from app.companies.repository import CompanyRepository
    from app.notifications.events import NotificationEventBus
    import uuid
    from datetime import datetime, timezone

    sub_service = SubscriptionService(db)
    invoice_repo = InvoiceRepository(db)
    company_repo = CompanyRepository(db)

    try:
        if event_type == "checkout.session.completed":
            # Payment was successful, subscription is now active
            session_data = event_data
            stripe_sub_id = session_data.get("subscription")
            customer_id   = session_data.get("customer")
            meta          = session_data.get("metadata", {})
            company_id_str = meta.get("company_id")
            plan_id_str    = meta.get("plan_id")

            if stripe_sub_id and company_id_str:
                # Fetch full subscription from Stripe
                stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                sub_service.handle_stripe_subscription_event(dict(stripe_sub), event_type)

        elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
            sub_service.handle_stripe_subscription_event(dict(event_data), event_type)

        elif event_type == "invoice.payment_succeeded":
            inv_data = event_data
            stripe_inv_id = inv_data.get("id")
            stripe_sub_id = inv_data.get("subscription")
            customer_id   = inv_data.get("customer")
            amount_paid   = (inv_data.get("amount_paid") or 0) / 100
            amount_due    = (inv_data.get("amount_due") or 0) / 100
            currency      = (inv_data.get("currency") or "usd").upper()

            # Resolve company from customer_id
            company_id = None
            meta = inv_data.get("subscription_details", {}).get("metadata", {}) or {}
            if not meta:
                meta = inv_data.get("metadata", {}) or {}
            company_id_str = meta.get("company_id")
            if company_id_str:
                try:
                    company_id = uuid.UUID(company_id_str)
                except Exception:
                    pass

            if company_id and not invoice_repo.get_by_provider_id(stripe_inv_id):
                period_start = datetime.fromtimestamp(inv_data["period_start"], tz=timezone.utc) if inv_data.get("period_start") else None
                period_end   = datetime.fromtimestamp(inv_data["period_end"], tz=timezone.utc)   if inv_data.get("period_end")   else None
                invoice_repo.create({
                    "company_id": company_id,
                    "provider": "stripe",
                    "provider_invoice_id": stripe_inv_id,
                    "provider_payment_id": inv_data.get("payment_intent"),
                    "amount_due": amount_due,
                    "amount_paid": amount_paid,
                    "currency": currency,
                    "status": InvoiceStatus.PAID,
                    "period_start": period_start,
                    "period_end": period_end,
                    "invoice_pdf": inv_data.get("invoice_pdf"),
                    "hosted_url": inv_data.get("hosted_invoice_url"),
                    "paid_at": datetime.now(timezone.utc),
                })

            # Notify
            if company_id:
                NotificationEventBus.dispatch(
                    event_type="payment.success",
                    db=db,
                    company_id=company_id,
                    user_id=None,
                    data={"amount": amount_paid, "currency": currency, "invoice_id": stripe_inv_id}
                )

        elif event_type == "invoice.payment_failed":
            inv_data = event_data
            meta = inv_data.get("subscription_details", {}).get("metadata", {}) or {}
            company_id_str = meta.get("company_id")
            amount_due = (inv_data.get("amount_due") or 0) / 100
            currency   = (inv_data.get("currency") or "usd").upper()

            if company_id_str:
                try:
                    company_id = uuid.UUID(company_id_str)
                    NotificationEventBus.dispatch(
                        event_type="payment.failed",
                        db=db,
                        company_id=company_id,
                        user_id=None,
                        data={"amount": amount_due, "currency": currency}
                    )
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"[Stripe Webhook] Error processing event {event_type}: {e}", exc_info=True)
        # Return 200 anyway so Stripe doesn't retry indefinitely for processing errors
        return {"received": True, "warning": str(e)}

    return {"received": True, "event": event_type}


@router.post(
    "/razorpay",
    summary="Razorpay webhook endpoint",
    description="Receives and processes Razorpay webhook events. Verifies X-Razorpay-Signature header."
)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    db: Session = Depends(get_db)
):
    """Razorpay webhook handler with HMAC-SHA256 signature verification."""
    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=503, detail="Razorpay webhooks are not configured.")

    import hmac
    import hashlib

    payload = await request.body()

    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header.")

    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, x_razorpay_signature):
        logger.warning("[Razorpay Webhook] Invalid signature.")
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature.")

    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_type = data.get("event")
    event_data = data.get("payload", {})
    logger.info(f"[Razorpay Webhook] Received event: {event_type}")

    from app.notifications.events import NotificationEventBus
    from app.payments.subscriptions.service import SubscriptionService
    from app.payments.subscriptions.model import SubscriptionStatus
    from app.payments.invoices.repository import InvoiceRepository
    from app.payments.invoices.model import InvoiceStatus
    from app.companies.repository import CompanyRepository
    import uuid
    from datetime import datetime, timezone

    try:
        if event_type == "payment.captured":
            payment = event_data.get("payment", {}).get("entity", {})
            notes = payment.get("notes", {})
            company_id_str = notes.get("company_id")
            plan_id_str = notes.get("plan_id")
            amount = (payment.get("amount") or 0) / 100
            currency = (payment.get("currency") or "INR")
            razorpay_payment_id = payment.get("id")
            razorpay_order_id = payment.get("order_id")

            if company_id_str:
                company_id = uuid.UUID(company_id_str)
                sub_service = SubscriptionService(db)
                invoice_repo = InvoiceRepository(db)

                # --- Activate subscription ---
                sub = sub_service.sub_repo.get_active_by_company(company_id)
                # Also look for an INCOMPLETE sub matching this order
                if not sub and razorpay_order_id:
                    from sqlalchemy import select
                    from app.payments.subscriptions.model import Subscription
                    sub = db.execute(
                        select(Subscription).where(Subscription.payment_id == razorpay_order_id)
                    ).scalar_one_or_none()

                if sub:
                    sub_service.sub_repo.update(sub, {
                        "status": SubscriptionStatus.ACTIVE,
                        "payment_id": razorpay_payment_id,
                    })

                    # --- Create Invoice (idempotent) ---
                    if razorpay_payment_id and not invoice_repo.get_by_provider_id(razorpay_payment_id):
                        plan = sub_service.plan_repo.get_by_id(sub.plan_id)
                        invoice_repo.create({
                            "company_id": company_id,
                            "subscription_id": sub.id,
                            "provider": "razorpay",
                            "provider_payment_id": razorpay_payment_id,
                            "amount_due": float(plan.amount) if plan else amount,
                            "amount_paid": amount,
                            "currency": currency,
                            "status": InvoiceStatus.PAID,
                            "paid_at": datetime.now(timezone.utc),
                        })

                    # --- Activate company plan ---
                    if plan_id_str:
                        try:
                            plan = sub_service.plan_repo.get_by_id(uuid.UUID(plan_id_str))
                            if plan:
                                sub_service._activate_company_plan(company_id, plan)
                        except Exception as exc:
                            logger.error(f"[Razorpay Webhook] Failed to activate company plan: {exc}")

                # --- Dispatch notifications ---
                NotificationEventBus.dispatch(
                    event_type="payment.success",
                    db=db,
                    company_id=company_id,
                    user_id=None,
                    data={"amount": amount, "currency": currency, "payment_id": razorpay_payment_id}
                )
                NotificationEventBus.dispatch(
                    event_type="subscription.created",
                    db=db,
                    company_id=company_id,
                    user_id=None,
                    data={"plan_name": notes.get("plan_name", "your selected")}
                )

        elif event_type == "payment.failed":
            payment = event_data.get("payment", {}).get("entity", {})
            notes = payment.get("notes", {})
            company_id_str = notes.get("company_id")
            amount = (payment.get("amount") or 0) / 100
            currency = (payment.get("currency") or "INR")

            if company_id_str:
                company_id = uuid.UUID(company_id_str)
                NotificationEventBus.dispatch(
                    event_type="payment.failed",
                    db=db,
                    company_id=company_id,
                    user_id=None,
                    data={"amount": amount, "currency": currency}
                )

        elif event_type == "subscription.activated":
            sub_entity = event_data.get("subscription", {}).get("entity", {})
            razorpay_sub_id = sub_entity.get("id")
            razorpay_order_id = sub_entity.get("payment_id")  # linked order/payment
            notes = sub_entity.get("notes", {})
            company_id_str = notes.get("company_id")
            plan_id_str = notes.get("plan_id")

            logger.info(f"[Razorpay Webhook] Subscription activated: {razorpay_sub_id}")

            if company_id_str:
                company_id = uuid.UUID(company_id_str)
                sub_service = SubscriptionService(db)

                # Find subscription by provider order/payment id
                from sqlalchemy import select
                from app.payments.subscriptions.model import Subscription
                sub = None
                if razorpay_order_id:
                    sub = db.execute(
                        select(Subscription).where(Subscription.payment_id == razorpay_order_id)
                    ).scalar_one_or_none()
                if not sub:
                    sub = sub_service.sub_repo.get_active_by_company(company_id)

                if sub:
                    sub_service.sub_repo.update(sub, {
                        "status": SubscriptionStatus.ACTIVE,
                        "provider_subscription_id": razorpay_sub_id,
                    })

                if plan_id_str:
                    try:
                        plan = sub_service.plan_repo.get_by_id(uuid.UUID(plan_id_str))
                        if plan:
                            sub_service._activate_company_plan(company_id, plan)
                    except Exception as exc:
                        logger.error(f"[Razorpay Webhook] Failed to activate company plan: {exc}")

                NotificationEventBus.dispatch(
                    event_type="subscription.created",
                    db=db,
                    company_id=company_id,
                    user_id=None,
                    data={"plan_name": notes.get("plan_name", "your selected")}
                )

    except Exception as e:
        logger.error(f"[Razorpay Webhook] Error processing {event_type}: {e}", exc_info=True)

    return {"received": True, "event": event_type}

