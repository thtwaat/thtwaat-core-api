"""Bug #1 regression: the legacy one-time Razorpay Order flow can complete
via TWO independent paths for the same payment — the browser-triggered
POST /razorpay/verify call, and Razorpay's own payment.captured webhook.
Either can arrive first. Exactly one PAID invoice and exactly one credit
grant/plan activation must result, regardless of ordering or duplicate
delivery.

These tests wire the real SubscriptionService.verify_razorpay_payment
together with the real razorpay_webhook payment.captured handler against a
single shared fake invoice ledger (mirroring the real DB-enforced
create_idempotent_by_payment_id semantics), so the assertions exercise the
actual production code paths rather than just call-count bookkeeping on a
fully mocked service.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.database.orm_bootstrap import register_orm_models

register_orm_models()

from app.payments.invoices.model import InvoiceStatus
from app.payments.subscriptions.model import SubscriptionProvider, SubscriptionStatus
from app.payments.subscriptions.schema import RazorpayVerifyRequest
from app.payments.subscriptions.service import SubscriptionService
from app.payments.webhooks.router import razorpay_webhook

WEBHOOK_SECRET = "whsec_test_razorpay_webhook_secret"
RAZORPAY_KEY_SECRET = "test_razorpay_secret_key"

COMPANY_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
ORDER_ID = "order_shared_1"
PAYMENT_ID = "pay_shared_1"


class FakeInvoiceRepo:
    """Mirrors InvoiceRepository's payment-id-keyed idempotency (the DB
    unique index is what makes this authoritative in production; this fake
    reproduces the same get-or-create contract without a real database)."""

    def __init__(self):
        self._by_payment_id: dict[str, SimpleNamespace] = {}
        self.create_calls = 0

    def get_by_provider_payment_id(self, payment_id):
        return self._by_payment_id.get(payment_id)

    def create_idempotent_by_payment_id(self, data: dict):
        payment_id = data.get("provider_payment_id")
        existing = self._by_payment_id.get(payment_id) if payment_id else None
        if existing:
            return existing, False
        invoice = SimpleNamespace(id=uuid.uuid4(), **data)
        if payment_id:
            self._by_payment_id[payment_id] = invoice
        self.create_calls += 1
        return invoice, True


def _plan() -> SimpleNamespace:
    return SimpleNamespace(
        id=PLAN_ID,
        name="starter",
        amount=Decimal("999.00"),
        currency="INR",
        is_active=True,
        max_users=5,
        max_apps=1,
        ai_credits=Decimal("100"),
    )


def _sub(**overrides) -> SimpleNamespace:
    base = dict(
        id=uuid.uuid4(),
        company_id=COMPANY_ID,
        plan_id=PLAN_ID,
        provider=SubscriptionProvider.RAZORPAY,
        status=SubscriptionStatus.INCOMPLETE,
        payment_id=ORDER_ID,
        invoice_id=None,
        metadata_={"razorpay_order_id": ORDER_ID, "plan_id": str(PLAN_ID)},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _apply_update(sub, data: dict):
    for key, value in data.items():
        setattr(sub, key, value)
    return sub


def _verify_service(sub, plan, invoice_repo) -> SubscriptionService:
    svc = SubscriptionService(db=MagicMock())
    svc.sub_repo = MagicMock()
    svc.plan_repo = MagicMock()
    svc.company_repo = MagicMock()
    svc.invoice_repo = invoice_repo
    svc.sub_repo.get_by_payment_id.return_value = sub
    # No subscription_id-based lookup configured by default — tests that need
    # the "already-verified via webhook" early-return path set
    # get_active_by_company explicitly instead, exercising that fallback on
    # purpose rather than by incidental Mock truthiness.
    svc.sub_repo.get_by_id.return_value = None
    svc.plan_repo.get_by_id.return_value = plan
    svc.sub_repo.update.side_effect = _apply_update
    return svc


def _verify_sig(order_id: str, payment_id: str) -> str:
    msg = f"{order_id}|{payment_id}"
    return hmac.new(RAZORPAY_KEY_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _captured_payload(*, payment_id=PAYMENT_ID, order_id=ORDER_ID, company_id=COMPANY_ID, plan_id=PLAN_ID):
    return json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": order_id,
                    "amount": 99900,
                    "currency": "INR",
                    "notes": {"company_id": str(company_id), "plan_id": str(plan_id)},
                }
            }
        },
    }).encode()


def _webhook_sig(payload: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()


class _FakeRequest:
    def __init__(self, body: bytes):
        self._body = body

    async def body(self) -> bytes:
        return self._body


def _fresh_claim_db() -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr("app.payments.webhooks.router.settings.RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_SECRET", RAZORPAY_KEY_SECRET)


async def _fire_payment_captured_webhook(sub, plan, invoice_repo):
    """Runs the real razorpay_webhook payment.captured branch against a
    SubscriptionService double sharing the same sub/plan/invoice state."""
    mock_sub_service = MagicMock()
    mock_sub_service.sub_repo.get_active_by_company.return_value = sub
    mock_sub_service.plan_repo.get_by_id.return_value = plan

    payload = _captured_payload()
    with patch("app.payments.subscriptions.service.SubscriptionService", return_value=mock_sub_service), \
         patch("app.payments.invoices.repository.InvoiceRepository", return_value=invoice_repo):
        await razorpay_webhook(
            request=_FakeRequest(payload),
            x_razorpay_signature=_webhook_sig(payload),
            db=_fresh_claim_db(),
        )
    return mock_sub_service


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_then_webhook_creates_exactly_one_invoice_and_one_activation():
    plan = _plan()
    sub = _sub(status=SubscriptionStatus.ACTIVE)
    invoice_repo = FakeInvoiceRepo()

    verify_svc = _verify_service(sub, plan, invoice_repo)
    with patch.object(verify_svc, "_activate_company_plan") as verify_activate:
        verify_svc.verify_razorpay_payment(
            COMPANY_ID,
            RazorpayVerifyRequest(
                razorpay_order_id=ORDER_ID,
                razorpay_payment_id=PAYMENT_ID,
                razorpay_signature=_verify_sig(ORDER_ID, PAYMENT_ID),
                plan_id=PLAN_ID,
            ),
        )
    assert invoice_repo.create_calls == 1
    verify_activate.assert_called_once()

    # payment.captured now arrives for the same payment, after verify already
    # activated it (sub.status is ACTIVE, matching webhook's active-company lookup).
    webhook_sub_service = await _fire_payment_captured_webhook(sub, plan, invoice_repo)

    assert invoice_repo.create_calls == 1, "webhook must not create a second invoice"
    webhook_sub_service._activate_company_plan.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_webhook_then_verify_creates_exactly_one_invoice_and_one_activation():
    plan = _plan()
    sub = _sub(status=SubscriptionStatus.INCOMPLETE)
    invoice_repo = FakeInvoiceRepo()

    webhook_sub_service = await _fire_payment_captured_webhook(sub, plan, invoice_repo)
    assert invoice_repo.create_calls == 1
    webhook_sub_service._activate_company_plan.assert_called_once()

    # Webhook flips the shared `sub` to ACTIVE via its own sub_repo.update mock,
    # but that mock doesn't touch the real `sub` object — mirror what the real
    # repository call would have done so verify's own lookup sees it as active.
    sub.status = SubscriptionStatus.ACTIVE

    # /razorpay/verify now runs for the same payment (browser was slow to
    # call back). Its own early idempotent-return path must catch this via
    # the shared invoice ledger.
    verify_svc = _verify_service(sub, plan, invoice_repo)
    with patch.object(verify_svc, "_activate_company_plan") as verify_activate:
        verify_svc.sub_repo.get_active_by_company.return_value = sub
        result = verify_svc.verify_razorpay_payment(
            COMPANY_ID,
            RazorpayVerifyRequest(
                razorpay_order_id=ORDER_ID,
                razorpay_payment_id=PAYMENT_ID,
                razorpay_signature=_verify_sig(ORDER_ID, PAYMENT_ID),
                plan_id=PLAN_ID,
            ),
        )

    assert invoice_repo.create_calls == 1, "verify must not create a second invoice"
    verify_activate.assert_not_called()
    assert result is sub


@pytest.mark.unit
@pytest.mark.asyncio
async def test_payment_captured_redelivered_creates_exactly_one_invoice():
    plan = _plan()
    sub = _sub(status=SubscriptionStatus.INCOMPLETE)
    invoice_repo = FakeInvoiceRepo()

    first = await _fire_payment_captured_webhook(sub, plan, invoice_repo)
    sub.status = SubscriptionStatus.ACTIVE
    second = await _fire_payment_captured_webhook(sub, plan, invoice_repo)

    assert invoice_repo.create_calls == 1
    first._activate_company_plan.assert_called_once()
    second._activate_company_plan.assert_not_called()
