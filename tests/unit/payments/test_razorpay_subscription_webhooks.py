"""Razorpay recurring-lifecycle webhook handlers: subscription.charged
(renewal), subscription.pending (mid-retry, no downgrade), subscription.halted
(final failure -> downgrade). Each proves the local Subscription/Invoice
state is written correctly and that a duplicate charge event never creates a
second invoice.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.database.orm_bootstrap import register_orm_models

register_orm_models()

from app.payments.subscriptions.model import SubscriptionStatus
from app.payments.webhooks.router import razorpay_webhook

WEBHOOK_SECRET = "whsec_test_razorpay_webhook_secret"


def _sign(payload_bytes: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


class _FakeRequest:
    def __init__(self, body: bytes):
        self._body = body

    async def body(self) -> bytes:
        return self._body


def _fresh_db() -> MagicMock:
    """Mock DB whose claim_webhook_event lookup finds nothing (first delivery)."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def _charged_payload(*, sub_id="sub_abc", payment_id="pay_1", plan_id=None, amount=99900,
                      current_start=1_700_000_000, current_end=1_702_678_400):
    return json.dumps({
        "event": "subscription.charged",
        "payload": {
            "subscription": {
                "entity": {
                    "id": sub_id,
                    "current_start": current_start,
                    "current_end": current_end,
                    "notes": {"plan_id": str(plan_id) if plan_id else None},
                }
            },
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": amount,
                    "currency": "INR",
                    "notes": {},
                }
            },
        },
    }).encode()


def _pending_payload(sub_id="sub_abc"):
    return json.dumps({
        "event": "subscription.pending",
        "payload": {"subscription": {"entity": {"id": sub_id, "notes": {}}}},
    }).encode()


def _halted_payload(sub_id="sub_abc"):
    return json.dumps({
        "event": "subscription.halted",
        "payload": {"subscription": {"entity": {"id": sub_id, "notes": {}}}},
    }).encode()


def _activated_payload(*, sub_id="sub_abc", plan_id=None,
                        current_start=1_700_000_000, current_end=1_702_678_400):
    return json.dumps({
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": sub_id,
                    "current_start": current_start,
                    "current_end": current_end,
                    "notes": {"plan_id": str(plan_id) if plan_id else None},
                }
            }
        },
    }).encode()


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    monkeypatch.setattr(
        "app.payments.webhooks.router.settings.RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET
    )


def _fake_sub(*, plan_id, status=SubscriptionStatus.ACTIVE):
    from types import SimpleNamespace
    return SimpleNamespace(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        plan_id=plan_id,
        status=status,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subscription_charged_updates_period_and_creates_invoice_once():
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id)
    payload = _charged_payload(plan_id=plan_id)
    sig = _sign(payload)
    db = _fresh_db()

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub
    mock_sub_service.plan_repo.get_by_id.return_value = MagicMock(amount=999)

    mock_invoice_repo = MagicMock()
    mock_invoice_repo.create_idempotent_by_payment_id.return_value = (MagicMock(), True)

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service), \
         patch("app.payments.invoices.repository.InvoiceRepository", return_value=mock_invoice_repo):
        result = await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert result["received"] is True

    update_args = mock_sub_service.sub_repo.update.call_args[0]
    updated_sub, updated_data = update_args
    assert updated_sub is sub
    assert updated_data["status"] == SubscriptionStatus.ACTIVE
    assert updated_data["current_period_start"] is not None
    assert updated_data["current_period_end"] is not None
    assert updated_data["payment_id"] == "pay_1"

    mock_invoice_repo.create_idempotent_by_payment_id.assert_called_once()
    invoice_data = mock_invoice_repo.create_idempotent_by_payment_id.call_args[0][0]
    assert invoice_data["provider_payment_id"] == "pay_1"
    assert invoice_data["provider"] == "razorpay"

    # Entitlement sync happens every delivery (idempotent); the credit grant
    # only happens because this call actually created the invoice.
    mock_sub_service._sync_company_plan_metadata.assert_called_once()
    mock_sub_service._grant_plan_credits.assert_called_once()
    # The combined one-shot helper must never be used by the recurring path —
    # it would double-grant credits alongside subscription.activated.
    mock_sub_service._activate_company_plan.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_duplicate_subscription_charged_does_not_create_second_invoice():
    """Simulates a re-delivered/duplicate charge event for a payment that
    already has an invoice on file (e.g. a different Razorpay event_id
    referencing the same payment) — must update state harmlessly without
    inserting a second ledger row or granting credits twice."""
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id)
    payload = _charged_payload(plan_id=plan_id, payment_id="pay_dup")
    sig = _sign(payload)
    db = _fresh_db()

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub
    mock_sub_service.plan_repo.get_by_id.return_value = MagicMock(amount=999)

    mock_invoice_repo = MagicMock()
    existing_invoice = MagicMock()
    mock_invoice_repo.create_idempotent_by_payment_id.return_value = (existing_invoice, False)

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service), \
         patch("app.payments.invoices.repository.InvoiceRepository", return_value=mock_invoice_repo):
        result = await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert result["received"] is True
    mock_invoice_repo.create_idempotent_by_payment_id.assert_called_once()
    # Status/period still resynced even when the invoice already exists.
    mock_sub_service.sub_repo.update.assert_called_once()
    mock_sub_service._sync_company_plan_metadata.assert_called_once()
    mock_sub_service._grant_plan_credits.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subscription_activated_syncs_metadata_without_granting_credits():
    """subscription.activated must sync plan/limits but must NEVER grant AI
    credits — subscription.charged (below) is the single authoritative event
    for that, since Razorpay also sends it for the same first cycle as a
    genuinely distinct event that webhook-level dedup will not collapse."""
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id)
    payload = _activated_payload(plan_id=plan_id)
    sig = _sign(payload)
    db = _fresh_db()

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub
    mock_sub_service.plan_repo.get_by_id.return_value = MagicMock(amount=999)

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service):
        result = await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert result["received"] is True
    mock_sub_service._sync_company_plan_metadata.assert_called_once()
    mock_sub_service._grant_plan_credits.assert_not_called()
    mock_sub_service._activate_company_plan.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_activated_then_first_charged_grants_credits_exactly_once():
    """The real-world sequence for a brand-new subscription: Razorpay sends
    subscription.activated, then subscription.charged for the same first
    cycle, as two distinct events. Credits must be granted exactly once
    across both deliveries, not once per event."""
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id)

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub
    mock_sub_service.plan_repo.get_by_id.return_value = MagicMock(amount=999)

    mock_invoice_repo = MagicMock()
    mock_invoice_repo.create_idempotent_by_payment_id.return_value = (MagicMock(), True)

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service), \
         patch("app.payments.invoices.repository.InvoiceRepository", return_value=mock_invoice_repo):
        activated_payload = _activated_payload(plan_id=plan_id)
        await razorpay_webhook(
            request=_FakeRequest(activated_payload),
            x_razorpay_signature=_sign(activated_payload),
            db=_fresh_db(),
        )

        charged_payload = _charged_payload(plan_id=plan_id, payment_id="pay_first_cycle")
        await razorpay_webhook(
            request=_FakeRequest(charged_payload),
            x_razorpay_signature=_sign(charged_payload),
            db=_fresh_db(),
        )

    mock_sub_service._grant_plan_credits.assert_called_once()
    mock_sub_service._activate_company_plan.assert_not_called()
    # Metadata sync is idempotent and legitimately runs on both deliveries.
    assert mock_sub_service._sync_company_plan_metadata.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_first_charged_redelivered_grants_credits_once():
    """Razorpay (or a reclaimed unprocessed BillingWebhookEvent row) resends
    the exact same charge event twice — the payment-id-keyed invoice
    idempotency must make the second delivery a no-op for credits."""
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id)

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub
    mock_sub_service.plan_repo.get_by_id.return_value = MagicMock(amount=999)

    invoice = MagicMock()
    mock_invoice_repo = MagicMock()
    mock_invoice_repo.create_idempotent_by_payment_id.side_effect = [
        (invoice, True),
        (invoice, False),
    ]

    payload = _charged_payload(plan_id=plan_id, payment_id="pay_redelivered")

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service), \
         patch("app.payments.invoices.repository.InvoiceRepository", return_value=mock_invoice_repo):
        await razorpay_webhook(request=_FakeRequest(payload), x_razorpay_signature=_sign(payload), db=_fresh_db())
        await razorpay_webhook(request=_FakeRequest(payload), x_razorpay_signature=_sign(payload), db=_fresh_db())

    assert mock_invoice_repo.create_idempotent_by_payment_id.call_count == 2
    mock_sub_service._grant_plan_credits.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_renewal_charged_with_new_payment_id_grants_credits_again():
    """Each real renewal (a genuinely new payment id) must still top up
    credits — the fix must not accidentally collapse distinct charges."""
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id)

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub
    mock_sub_service.plan_repo.get_by_id.return_value = MagicMock(amount=999)

    mock_invoice_repo = MagicMock()
    mock_invoice_repo.create_idempotent_by_payment_id.side_effect = [
        (MagicMock(), True),
        (MagicMock(), True),
    ]

    first = _charged_payload(plan_id=plan_id, payment_id="pay_cycle_1")
    second = _charged_payload(plan_id=plan_id, payment_id="pay_cycle_2")

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service), \
         patch("app.payments.invoices.repository.InvoiceRepository", return_value=mock_invoice_repo):
        await razorpay_webhook(request=_FakeRequest(first), x_razorpay_signature=_sign(first), db=_fresh_db())
        await razorpay_webhook(request=_FakeRequest(second), x_razorpay_signature=_sign(second), db=_fresh_db())

    assert mock_sub_service._grant_plan_credits.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subscription_pending_marks_past_due_without_downgrade():
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id, status=SubscriptionStatus.ACTIVE)
    payload = _pending_payload()
    sig = _sign(payload)
    db = _fresh_db()

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service):
        result = await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert result["received"] is True
    mock_sub_service.sub_repo.update.assert_called_once_with(
        sub, {"status": SubscriptionStatus.PAST_DUE}
    )
    # Must NOT downgrade while still inside Razorpay's retry lifecycle.
    mock_sub_service._downgrade_to_free.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subscription_halted_marks_unpaid_and_downgrades():
    plan_id = uuid.uuid4()
    sub = _fake_sub(plan_id=plan_id, status=SubscriptionStatus.PAST_DUE)
    payload = _halted_payload()
    sig = _sign(payload)
    db = _fresh_db()

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = sub

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service):
        result = await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert result["received"] is True
    updated_sub, updated_data = mock_sub_service.sub_repo.update.call_args[0]
    assert updated_sub is sub
    assert updated_data["status"] == SubscriptionStatus.UNPAID
    mock_sub_service._downgrade_to_free.assert_called_once_with(sub.company_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subscription_charged_unknown_subscription_is_logged_not_crashed():
    payload = _charged_payload(sub_id="sub_unknown")
    sig = _sign(payload)
    db = _fresh_db()

    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_by_provider_subscription_id.return_value = None

    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service):
        result = await razorpay_webhook(
            request=_FakeRequest(payload), x_razorpay_signature=sig, db=db
        )

    assert result["received"] is True
    mock_sub_service.sub_repo.update.assert_not_called()
