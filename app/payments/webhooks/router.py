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
    event_id = event.get("id") or f"stripe-{event_type}-{event_data.get('id')}"

    logger.info(f"[Stripe Webhook] Received event: {event_type}")

    from app.payments.billing_extras import (
        claim_webhook_event,
        mark_webhook_failed,
        mark_webhook_processed,
    )
    from app.payments.subscriptions.service import SubscriptionService
    from app.payments.invoices.repository import InvoiceRepository
    from app.payments.invoices.model import InvoiceStatus
    from app.companies.repository import CompanyRepository
    from app.notifications.events import NotificationEventBus
    import uuid
    from datetime import datetime, timezone

    claimed = claim_webhook_event(
        db,
        provider="stripe",
        event_id=str(event_id),
        event_type=event_type,
        payload={"type": event_type, "object_id": event_data.get("id")},
    )
    if claimed is None:
        return {"received": True, "event": event_type, "duplicate": True}

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

        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            sub_service.handle_stripe_subscription_event(dict(event_data), event_type)

        elif event_type in ("invoice.payment_succeeded", "invoice.paid"):
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

        mark_webhook_processed(db, claimed)
    except Exception as e:
        logger.error(f"[Stripe Webhook] Error processing event {event_type}: {e}", exc_info=True)
        mark_webhook_failed(db, claimed, str(e))
        # 5xx so Stripe retries; event stays unprocessed for reclaim.
        raise HTTPException(status_code=500, detail="Webhook processing failed; retry later")

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
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Razorpay webhooks are not configured.")

    import hmac
    import hashlib

    payload = await request.body()

    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header.")

    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
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
    event_id = (
        data.get("event_id")
        or (event_data.get("payment", {}) or {}).get("entity", {}).get("id")
        or (event_data.get("subscription", {}) or {}).get("entity", {}).get("id")
        or f"razorpay-{event_type}-{hash(payload)}"
    )
    logger.info(f"[Razorpay Webhook] Received event: {event_type}")

    from app.payments.billing_extras import (
        claim_webhook_event,
        mark_webhook_failed,
        mark_webhook_processed,
    )
    from app.notifications.events import NotificationEventBus
    from app.payments.subscriptions.service import SubscriptionService
    from app.payments.subscriptions.model import SubscriptionStatus
    from app.payments.invoices.repository import InvoiceRepository
    from app.payments.invoices.model import InvoiceStatus
    from app.companies.repository import CompanyRepository
    from app.payments.providers.razorpay import extract_subscription_period
    import uuid
    from datetime import datetime, timezone

    claimed = claim_webhook_event(
        db,
        provider="razorpay",
        event_id=str(event_id),
        event_type=str(event_type or "unknown"),
        payload={"event": event_type},
    )
    if claimed is None:
        return {"received": True, "event": event_type, "duplicate": True}

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

                    # --- Create Invoice (idempotent by provider_payment_id —
                    # DB-enforced via a unique index, not just this check, so
                    # this is safe even if /razorpay/verify creates the same
                    # payment's invoice concurrently). NOTE: the previous
                    # version of this check queried provider_invoice_id,
                    # which Razorpay never populates — it always missed the
                    # existing invoice and created a duplicate. ---
                    created = False
                    if razorpay_payment_id:
                        plan = sub_service.plan_repo.get_by_id(sub.plan_id)
                        _invoice, created = invoice_repo.create_idempotent_by_payment_id({
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

                    # --- Activate company plan + grant AI credits — only the
                    # first time this payment's invoice is actually created.
                    # /razorpay/verify may have already done this for the
                    # same payment if it ran first; doing it again here would
                    # double-grant credits for a single payment. ---
                    if created and plan_id_str:
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
            razorpay_order_id = sub_entity.get("payment_id")  # legacy order-flow fallback only
            notes = sub_entity.get("notes", {})
            company_id_str = notes.get("company_id")
            plan_id_str = notes.get("plan_id")

            logger.info(f"[Razorpay Webhook] Subscription activated: {razorpay_sub_id}")

            sub_service = SubscriptionService(db)

            # Real recurring subscriptions are created with
            # provider_subscription_id already set at checkout time (see
            # SubscriptionService.create_razorpay_subscription) — look up by
            # that first. The order-id/active-company fallbacks below only
            # matter for older rows that predate that flow.
            sub = None
            if razorpay_sub_id:
                sub = sub_service.sub_repo.get_by_provider_subscription_id(razorpay_sub_id)
            if not sub and razorpay_order_id:
                from sqlalchemy import select
                from app.payments.subscriptions.model import Subscription
                sub = db.execute(
                    select(Subscription).where(Subscription.payment_id == razorpay_order_id)
                ).scalar_one_or_none()
            if not sub and company_id_str:
                sub = sub_service.sub_repo.get_active_by_company(uuid.UUID(company_id_str))

            if sub:
                update = {
                    "status": SubscriptionStatus.ACTIVE,
                    "provider_subscription_id": razorpay_sub_id,
                }
                start, end = extract_subscription_period(sub_entity)
                if start:
                    update["current_period_start"] = start
                if end:
                    update["current_period_end"] = end
                sub_service.sub_repo.update(sub, update)

                company_id = sub.company_id
                effective_plan_id_str = plan_id_str
                if not effective_plan_id_str:
                    effective_plan_id_str = str(sub.plan_id)
                try:
                    plan = sub_service.plan_repo.get_by_id(uuid.UUID(effective_plan_id_str))
                    if plan:
                        # Metadata/limits sync only — NOT the credit grant.
                        # Razorpay also sends subscription.charged for this
                        # same first cycle (a distinct event with its own
                        # event_id, so the webhook-dedup layer does not and
                        # should not collapse the two); subscription.charged
                        # is the single authoritative place credits are
                        # granted, keyed to its payment id. Calling the full
                        # _activate_company_plan here too would double-grant
                        # credits on every new subscription's first cycle.
                        sub_service._sync_company_plan_metadata(company_id, plan)
                except Exception as exc:
                    logger.error(f"[Razorpay Webhook] Failed to sync company plan: {exc}")

                NotificationEventBus.dispatch(
                    event_type="subscription.created",
                    db=db,
                    company_id=company_id,
                    user_id=None,
                    data={"plan_name": notes.get("plan_name", "your selected")}
                )
            else:
                logger.warning(
                    f"[Razorpay Webhook] subscription.activated: no local subscription found "
                    f"for razorpay_sub_id={razorpay_sub_id}"
                )

        elif event_type == "subscription.charged":
            # The actual RENEWAL event — fired on every successful billing
            # cycle charge, including the very first one. This is the only
            # place current_period_start/end and the invoice ledger are
            # authoritatively written for a Razorpay recurring subscription.
            sub_entity = event_data.get("subscription", {}).get("entity", {})
            payment_entity = event_data.get("payment", {}).get("entity", {})
            razorpay_sub_id = sub_entity.get("id")
            razorpay_payment_id = payment_entity.get("id")
            notes = sub_entity.get("notes", {}) or payment_entity.get("notes", {}) or {}
            plan_id_str = notes.get("plan_id")
            amount = (payment_entity.get("amount") or 0) / 100
            currency = (payment_entity.get("currency") or "INR")

            sub_service = SubscriptionService(db)
            invoice_repo = InvoiceRepository(db)

            sub = None
            if razorpay_sub_id:
                sub = sub_service.sub_repo.get_by_provider_subscription_id(razorpay_sub_id)
            if not sub:
                logger.warning(
                    f"[Razorpay Webhook] subscription.charged: no local subscription found "
                    f"for razorpay_sub_id={razorpay_sub_id}"
                )
            else:
                start, end = extract_subscription_period(sub_entity)
                update = {"status": SubscriptionStatus.ACTIVE}
                if start:
                    update["current_period_start"] = start
                if end:
                    update["current_period_end"] = end
                if razorpay_payment_id:
                    update["payment_id"] = razorpay_payment_id
                sub_service.sub_repo.update(sub, update)

                # Idempotent by provider_payment_id — DB-enforced via a
                # unique index (not just this pre-check), so a duplicate
                # delivery of the same charge event (Razorpay's own retries,
                # a re-claimed unprocessed event, or a genuine concurrent
                # race) can never create a second invoice for the same
                # payment.
                created = False
                if razorpay_payment_id:
                    plan = sub_service.plan_repo.get_by_id(sub.plan_id)
                    _invoice, created = invoice_repo.create_idempotent_by_payment_id({
                        "company_id": sub.company_id,
                        "subscription_id": sub.id,
                        "provider": "razorpay",
                        "provider_payment_id": razorpay_payment_id,
                        "amount_due": float(plan.amount) if plan else amount,
                        "amount_paid": amount,
                        "currency": currency,
                        "status": InvoiceStatus.PAID,
                        "period_start": start,
                        "period_end": end,
                        "paid_at": datetime.now(timezone.utc),
                    })

                effective_plan_id_str = plan_id_str or str(sub.plan_id)
                try:
                    plan = sub_service.plan_repo.get_by_id(uuid.UUID(effective_plan_id_str))
                    if plan:
                        # Metadata/limits sync every renewal (idempotent).
                        sub_service._sync_company_plan_metadata(sub.company_id, plan)
                        # Credit grant only for a genuinely new charge/payment
                        # id — this is the single authoritative place credits
                        # are granted for both the first cycle and every
                        # renewal (see subscription.activated above, which
                        # deliberately does not grant credits).
                        if created:
                            sub_service._grant_plan_credits(sub.company_id, plan)
                except Exception as exc:
                    logger.error(f"[Razorpay Webhook] Failed to activate company plan on charge: {exc}")

                NotificationEventBus.dispatch(
                    event_type="subscription.renewed",
                    db=db,
                    company_id=sub.company_id,
                    user_id=None,
                    data={"plan_name": notes.get("plan_name", "your")}
                )
                NotificationEventBus.dispatch(
                    event_type="payment.success",
                    db=db,
                    company_id=sub.company_id,
                    user_id=None,
                    data={"amount": amount, "currency": currency, "payment_id": razorpay_payment_id}
                )

        elif event_type == "subscription.pending":
            # Razorpay is mid-retry after a failed renewal charge — the
            # subscription is not yet halted. Per the audit's explicit
            # instruction: do NOT downgrade while still inside Razorpay's own
            # retry/collection lifecycle. Only subscription.halted (below) is
            # the final failure state.
            sub_entity = event_data.get("subscription", {}).get("entity", {})
            razorpay_sub_id = sub_entity.get("id")
            sub_service = SubscriptionService(db)
            sub = sub_service.sub_repo.get_by_provider_subscription_id(razorpay_sub_id) if razorpay_sub_id else None
            if sub:
                sub_service.sub_repo.update(sub, {"status": SubscriptionStatus.PAST_DUE})
                NotificationEventBus.dispatch(
                    event_type="payment.failed",
                    db=db,
                    company_id=sub.company_id,
                    user_id=None,
                    data={"amount": 0, "currency": "INR"}
                )
            else:
                logger.warning(
                    f"[Razorpay Webhook] subscription.pending: no local subscription found "
                    f"for razorpay_sub_id={razorpay_sub_id}"
                )

        elif event_type == "subscription.halted":
            # Razorpay has exhausted its retry schedule — this is the final
            # renewal failure state, not a transient one. Downgrade using the
            # same _downgrade_to_free path as a customer-initiated
            # cancellation (existing billing rule), but keep status=UNPAID
            # (not CANCELLED) so it stays distinguishable from a voluntary
            # cancellation, matching the Stripe status vocabulary already
            # used elsewhere in this file.
            sub_entity = event_data.get("subscription", {}).get("entity", {})
            razorpay_sub_id = sub_entity.get("id")
            sub_service = SubscriptionService(db)
            sub = sub_service.sub_repo.get_by_provider_subscription_id(razorpay_sub_id) if razorpay_sub_id else None
            if sub:
                sub_service.sub_repo.update(
                    sub,
                    {
                        "status": SubscriptionStatus.UNPAID,
                        "cancelled_at": datetime.now(timezone.utc),
                    },
                )
                sub_service._downgrade_to_free(sub.company_id)
                NotificationEventBus.dispatch(
                    event_type="payment.failed",
                    db=db,
                    company_id=sub.company_id,
                    user_id=None,
                    data={"amount": 0, "currency": "INR"}
                )
            else:
                logger.warning(
                    f"[Razorpay Webhook] subscription.halted: no local subscription found "
                    f"for razorpay_sub_id={razorpay_sub_id}"
                )

        elif event_type in ("subscription.cancelled", "subscription.canceled"):
            sub_entity = event_data.get("subscription", {}).get("entity", {})
            razorpay_sub_id = sub_entity.get("id")
            notes = sub_entity.get("notes", {}) or {}
            company_id_str = notes.get("company_id")
            sub_service = SubscriptionService(db)
            sub = None
            if razorpay_sub_id:
                sub = sub_service.sub_repo.get_by_provider_subscription_id(razorpay_sub_id)
            if not sub and company_id_str:
                sub = sub_service.sub_repo.get_active_by_company(uuid.UUID(company_id_str))
            if sub:
                sub_service.sub_repo.update(
                    sub,
                    {
                        "status": SubscriptionStatus.CANCELLED,
                        "cancelled_at": datetime.now(timezone.utc),
                        "cancel_at_period_end": False,
                    },
                )
                sub_service._downgrade_to_free(sub.company_id)

        elif event_type == "refund.processed":
            refund = event_data.get("refund", {}).get("entity", {}) or event_data.get("payment", {}).get("entity", {})
            notes = refund.get("notes", {}) or {}
            company_id_str = notes.get("company_id")
            amount = (refund.get("amount") or 0) / 100
            currency = (refund.get("currency") or "INR")
            if company_id_str:
                NotificationEventBus.dispatch(
                    event_type="payment.refunded",
                    db=db,
                    company_id=uuid.UUID(company_id_str),
                    user_id=None,
                    data={
                        "amount": amount,
                        "currency": currency,
                        "refund_id": refund.get("id"),
                        "payment_id": refund.get("payment_id"),
                    },
                )

        mark_webhook_processed(db, claimed)
    except Exception as e:
        logger.error(f"[Razorpay Webhook] Error processing {event_type}: {e}", exc_info=True)
        mark_webhook_failed(db, claimed, str(e))
        raise HTTPException(status_code=500, detail="Webhook processing failed; retry later")

    return {"received": True, "event": event_type}

