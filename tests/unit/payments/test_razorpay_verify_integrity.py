"""P0: Razorpay verify must use server-side order plan, never trust client plan_id."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.payments.invoices.model import InvoiceStatus
from app.payments.subscriptions.model import SubscriptionProvider, SubscriptionStatus
from app.payments.subscriptions.schema import RazorpayVerifyRequest
from app.payments.subscriptions.service import SubscriptionService


SECRET = "test_razorpay_secret_key"


def _sig(order_id: str, payment_id: str) -> str:
    msg = f"{order_id}|{payment_id}"
    return hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _plan(plan_id: uuid.UUID | None = None, *, name: str = "starter", amount: str = "10.00"):
    return SimpleNamespace(
        id=plan_id or uuid.uuid4(),
        name=name,
        amount=Decimal(amount),
        currency="INR",
        is_active=True,
        max_users=5,
        max_apps=1,
        ai_credits=Decimal("100"),
    )


def _sub(
    *,
    company_id: uuid.UUID,
    plan_id: uuid.UUID,
    order_id: str,
    status: SubscriptionStatus = SubscriptionStatus.INCOMPLETE,
    payment_id: str | None = None,
    metadata: dict | None = None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_id,
        plan_id=plan_id,
        provider=SubscriptionProvider.RAZORPAY,
        status=status,
        payment_id=payment_id or order_id,
        invoice_id=None,
        metadata_=metadata
        or {
            "razorpay_order_id": order_id,
            "plan_id": str(plan_id),
        },
    )


def _service() -> SubscriptionService:
    svc = SubscriptionService(db=MagicMock())
    svc.sub_repo = MagicMock()
    svc.plan_repo = MagicMock()
    svc.invoice_repo = MagicMock()
    svc.company_repo = MagicMock()
    return svc


def _verify_payload(order_id: str, payment_id: str, plan_id: uuid.UUID, *, bad_sig: bool = False):
    return RazorpayVerifyRequest(
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature="deadbeef" if bad_sig else _sig(order_id, payment_id),
        plan_id=plan_id,
    )


@pytest.fixture(autouse=True)
def _razorpay_secret(monkeypatch):
    monkeypatch.setattr(
        "app.payments.subscriptions.service.settings.RAZORPAY_KEY_SECRET",
        SECRET,
    )


@pytest.mark.unit
def test_verify_valid_payment_activates_trusted_plan():
    svc = _service()
    company_id = uuid.uuid4()
    plan = _plan()
    order_id = "order_valid_1"
    payment_id = "pay_valid_1"
    sub = _sub(company_id=company_id, plan_id=plan.id, order_id=order_id)

    svc.invoice_repo.get_by_provider_payment_id.return_value = None
    svc.sub_repo.get_by_payment_id.return_value = sub
    svc.plan_repo.get_by_id.return_value = plan
    svc.sub_repo.update.side_effect = lambda s, data: setattr(s, "status", data.get("status", s.status)) or s
    svc.invoice_repo.create.return_value = SimpleNamespace(id=uuid.uuid4())

    with patch.object(svc, "_activate_company_plan") as activate:
        result = svc.verify_razorpay_payment(
            company_id,
            _verify_payload(order_id, payment_id, plan.id),
        )

    assert result is sub
    activate.assert_called_once_with(company_id, plan)
    svc.plan_repo.get_by_id.assert_called_with(plan.id)
    created = svc.invoice_repo.create.call_args[0][0]
    assert created["provider_payment_id"] == payment_id
    assert created["status"] == InvoiceStatus.PAID


@pytest.mark.unit
def test_verify_rejects_modified_plan_id():
    svc = _service()
    company_id = uuid.uuid4()
    bound_plan = _plan()
    attacker_plan = _plan(name="enterprise", amount="999.00")
    order_id = "order_tamper_1"
    payment_id = "pay_tamper_1"
    sub = _sub(company_id=company_id, plan_id=bound_plan.id, order_id=order_id)

    svc.invoice_repo.get_by_provider_payment_id.return_value = None
    svc.sub_repo.get_by_payment_id.return_value = sub

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_payment(
            company_id,
            _verify_payload(order_id, payment_id, attacker_plan.id),
        )

    assert exc.value.status_code == 400
    assert "plan_id" in str(exc.value.detail).lower()
    svc.invoice_repo.create.assert_not_called()
    svc.plan_repo.get_by_id.assert_not_called()


@pytest.mark.unit
def test_verify_rejects_missing_order_mapping():
    svc = _service()
    company_id = uuid.uuid4()
    plan = _plan()
    order_id = "order_missing_1"
    payment_id = "pay_missing_1"

    svc.invoice_repo.get_by_provider_payment_id.return_value = None
    svc.sub_repo.get_by_payment_id.return_value = None
    svc.sub_repo.list_by_company.return_value = []

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_payment(
            company_id,
            _verify_payload(order_id, payment_id, plan.id),
        )

    assert exc.value.status_code == 400
    assert "order mapping" in str(exc.value.detail).lower()
    svc.invoice_repo.create.assert_not_called()


@pytest.mark.unit
def test_verify_duplicate_is_idempotent():
    svc = _service()
    company_id = uuid.uuid4()
    plan = _plan()
    order_id = "order_dup_1"
    payment_id = "pay_dup_1"
    sub = _sub(
        company_id=company_id,
        plan_id=plan.id,
        order_id=order_id,
        status=SubscriptionStatus.ACTIVE,
        payment_id=payment_id,
    )
    invoice = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_id,
        subscription_id=sub.id,
        provider_payment_id=payment_id,
    )

    svc.invoice_repo.get_by_provider_payment_id.return_value = invoice
    svc.sub_repo.get_by_id.return_value = sub

    with patch.object(svc, "_activate_company_plan") as activate:
        result = svc.verify_razorpay_payment(
            company_id,
            _verify_payload(order_id, payment_id, plan.id),
        )

    assert result is sub
    activate.assert_not_called()
    svc.invoice_repo.create.assert_not_called()


@pytest.mark.unit
def test_verify_rejects_invalid_signature():
    svc = _service()
    company_id = uuid.uuid4()
    plan = _plan()

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_payment(
            company_id,
            _verify_payload("order_bad", "pay_bad", plan.id, bad_sig=True),
        )

    assert exc.value.status_code == 400
    assert "signature" in str(exc.value.detail).lower()
    svc.sub_repo.get_by_payment_id.assert_not_called()
    svc.invoice_repo.create.assert_not_called()


@pytest.mark.unit
def test_trusted_plan_prefers_pending_plan_id_metadata():
    svc = _service()
    company_id = uuid.uuid4()
    current_plan = _plan(name="starter")
    pending_plan = _plan(name="growth", amount="50.00")
    order_id = "order_upgrade_1"
    payment_id = "pay_upgrade_1"
    sub = _sub(
        company_id=company_id,
        plan_id=current_plan.id,
        order_id=order_id,
        status=SubscriptionStatus.ACTIVE,
        metadata={
            "razorpay_order_id": order_id,
            "pending_plan_id": str(pending_plan.id),
        },
    )

    svc.invoice_repo.get_by_provider_payment_id.return_value = None
    svc.sub_repo.get_by_payment_id.return_value = sub
    svc.plan_repo.get_by_id.return_value = pending_plan
    svc.sub_repo.update.side_effect = lambda s, data: s
    svc.invoice_repo.create.return_value = SimpleNamespace(id=uuid.uuid4())

    with patch.object(svc, "_activate_company_plan") as activate:
        # Client must send the pending (ordered) plan, not the old active plan.
        svc.verify_razorpay_payment(
            company_id,
            _verify_payload(order_id, payment_id, pending_plan.id),
        )
        activate.assert_called_once_with(company_id, pending_plan)

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_payment(
            company_id,
            _verify_payload(order_id, payment_id, current_plan.id),
        )
    assert exc.value.status_code == 400
