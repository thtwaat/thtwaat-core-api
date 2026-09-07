"""cancel_subscription/resume_subscription for a real Razorpay recurring
subscription: cancellation must be requested as cancel_at_cycle_end (not an
immediate cancel), must not eagerly downgrade or set cancelled_at (the
subscription.cancelled webhook finalizes that), and resuming an already
cancel-scheduled Razorpay subscription must be refused rather than silently
desyncing local state from what Razorpay will actually do.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.payments.subscriptions.model import SubscriptionProvider
from app.payments.subscriptions.service import SubscriptionService


def _service() -> SubscriptionService:
    svc = SubscriptionService(db=MagicMock())
    svc.sub_repo = MagicMock()
    return svc


def _razorpay_sub(**overrides):
    base = dict(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        provider=SubscriptionProvider.RAZORPAY,
        provider_subscription_id="sub_live_1",
        cancel_at_period_end=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _razorpay_config(monkeypatch):
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_ID", "rzp_test_id")
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_SECRET", "rzp_test_secret")


@pytest.mark.unit
def test_cancel_requests_cancel_at_cycle_end_not_immediate():
    svc = _service()
    sub = _razorpay_sub()
    svc.sub_repo.get_active_by_company.return_value = sub
    svc.sub_repo.update.return_value = sub

    client = MagicMock()
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True):
        svc.cancel_subscription(sub.company_id)

    client.subscription.cancel.assert_called_once_with("sub_live_1", {"cancel_at_cycle_end": 1})


@pytest.mark.unit
def test_cancel_does_not_eagerly_set_cancelled_at_or_downgrade():
    """Local cancellation request only flags intent; the actual state
    transition (status=CANCELLED, cancelled_at, downgrade) is left to the
    subscription.cancelled webhook — mirrors the Stripe branch."""
    svc = _service()
    sub = _razorpay_sub()
    svc.sub_repo.get_active_by_company.return_value = sub
    svc.sub_repo.update.return_value = sub

    client = MagicMock()
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True):
        svc.cancel_subscription(sub.company_id)

    updated_data = svc.sub_repo.update.call_args[0][1]
    assert updated_data == {"cancel_at_period_end": True}
    assert "cancelled_at" not in updated_data
    assert "status" not in updated_data


@pytest.mark.unit
def test_cancel_legacy_row_without_provider_subscription_id_is_local_only():
    svc = _service()
    sub = _razorpay_sub(provider_subscription_id=None)
    svc.sub_repo.get_active_by_company.return_value = sub
    svc.sub_repo.update.return_value = sub

    with patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True):
        svc.cancel_subscription(sub.company_id)

    svc.sub_repo.update.assert_called_once_with(sub, {"cancel_at_period_end": True})


@pytest.mark.unit
def test_resume_is_refused_for_razorpay_subscription_pending_cancellation():
    svc = _service()
    sub = _razorpay_sub(cancel_at_period_end=True)
    svc.sub_repo.get_active_by_company.return_value = sub

    with pytest.raises(HTTPException) as exc:
        svc.resume_subscription(sub.company_id)

    assert exc.value.status_code == 400
    svc.sub_repo.update.assert_not_called()
