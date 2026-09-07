"""SubscriptionService.verify_razorpay_subscription_payment: verifies the
first-charge signature but must NEVER activate the subscription itself —
only the subscription.charged/activated webhook is authoritative for that.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.payments.subscriptions.model import SubscriptionStatus
from app.payments.subscriptions.schema import RazorpaySubscriptionVerifyRequest
from app.payments.subscriptions.service import SubscriptionService

SECRET = "test_razorpay_secret_key"


def _sig(payment_id: str, subscription_id: str) -> str:
    msg = f"{payment_id}|{subscription_id}"
    return hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _sub(*, company_id, plan_id, sub_id="sub_abc", status=SubscriptionStatus.INCOMPLETE, metadata=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_id,
        plan_id=plan_id,
        provider_subscription_id=sub_id,
        status=status,
        metadata_=metadata or {"pending_plan_id": str(plan_id)},
    )


def _service() -> SubscriptionService:
    svc = SubscriptionService(db=MagicMock())
    svc.sub_repo = MagicMock()
    svc.plan_repo = MagicMock()
    return svc


def _payload(sub_id, payment_id, plan_id, *, bad_sig=False):
    return RazorpaySubscriptionVerifyRequest(
        razorpay_subscription_id=sub_id,
        razorpay_payment_id=payment_id,
        razorpay_signature="deadbeef" if bad_sig else _sig(payment_id, sub_id),
        plan_id=plan_id,
    )


@pytest.fixture(autouse=True)
def _razorpay_secret(monkeypatch):
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_ID", "rzp_test_id")
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_SECRET", SECRET)


@pytest.mark.unit
def test_valid_signature_does_not_activate_or_touch_status():
    svc = _service()
    company_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    sub = _sub(company_id=company_id, plan_id=plan_id)
    svc.sub_repo.get_by_provider_subscription_id.return_value = sub
    svc.sub_repo.update.return_value = sub

    result = svc.verify_razorpay_subscription_payment(
        company_id, _payload("sub_abc", "pay_1", plan_id)
    )

    assert result is sub
    # Never flips status here — only a webhook may do that.
    update_call = svc.sub_repo.update.call_args
    assert update_call is not None
    updated_sub, updated_data = update_call[0]
    assert "status" not in updated_data
    assert updated_data["metadata_"]["first_charge_verified_payment_id"] == "pay_1"


@pytest.mark.unit
def test_already_active_subscription_is_left_untouched_idempotent():
    svc = _service()
    company_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    sub = _sub(company_id=company_id, plan_id=plan_id, status=SubscriptionStatus.ACTIVE)
    svc.sub_repo.get_by_provider_subscription_id.return_value = sub

    result = svc.verify_razorpay_subscription_payment(
        company_id, _payload("sub_abc", "pay_1", plan_id)
    )

    assert result is sub
    svc.sub_repo.update.assert_not_called()


@pytest.mark.unit
def test_rejects_invalid_signature():
    svc = _service()
    company_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_subscription_payment(
            company_id, _payload("sub_abc", "pay_1", plan_id, bad_sig=True)
        )

    assert exc.value.status_code == 400
    svc.sub_repo.get_by_provider_subscription_id.assert_not_called()


@pytest.mark.unit
def test_rejects_subscription_owned_by_a_different_company():
    svc = _service()
    plan_id = uuid.uuid4()
    sub = _sub(company_id=uuid.uuid4(), plan_id=plan_id)
    svc.sub_repo.get_by_provider_subscription_id.return_value = sub

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_subscription_payment(
            uuid.uuid4(),  # different company
            _payload("sub_abc", "pay_1", plan_id),
        )

    assert exc.value.status_code == 400
    svc.sub_repo.update.assert_not_called()


@pytest.mark.unit
def test_rejects_unknown_subscription_id():
    svc = _service()
    svc.sub_repo.get_by_provider_subscription_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_subscription_payment(
            uuid.uuid4(), _payload("sub_missing", "pay_1", uuid.uuid4())
        )

    assert exc.value.status_code == 400


@pytest.mark.unit
def test_rejects_plan_id_mismatch_with_trusted_metadata():
    svc = _service()
    company_id = uuid.uuid4()
    bound_plan_id = uuid.uuid4()
    attacker_plan_id = uuid.uuid4()
    sub = _sub(company_id=company_id, plan_id=bound_plan_id)
    svc.sub_repo.get_by_provider_subscription_id.return_value = sub

    with pytest.raises(HTTPException) as exc:
        svc.verify_razorpay_subscription_payment(
            company_id, _payload("sub_abc", "pay_1", attacker_plan_id)
        )

    assert exc.value.status_code == 400
    svc.sub_repo.update.assert_not_called()
