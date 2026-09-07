"""SubscriptionService.reconcile_razorpay_subscriptions: the safety net for
a dropped/delayed webhook. Only ever touches real recurring subscriptions
(provider_subscription_id set) whose local period lapsed a while ago, and
always re-checks the actual state with Razorpay before changing anything —
never assumes non-payment purely from a missing webhook.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.payments.subscriptions.model import SubscriptionStatus
from app.payments.subscriptions.service import SubscriptionService


def _stale_sub(**overrides):
    base = dict(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        provider_subscription_id="sub_stale_1",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) - timedelta(hours=48),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service_with_stale(stale_rows) -> SubscriptionService:
    svc = SubscriptionService(db=MagicMock())
    svc.sub_repo = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = stale_rows
    svc.db.execute.return_value.scalars.return_value = scalars_mock
    return svc


@pytest.fixture(autouse=True)
def _razorpay_config(monkeypatch):
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_ID", "rzp_test_id")
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_SECRET", "rzp_test_secret")


@pytest.mark.unit
def test_disabled_provider_skips_without_touching_db():
    svc = SubscriptionService(db=MagicMock())
    with patch("app.payments.subscriptions.service.razorpay_enabled", return_value=False):
        result = svc.reconcile_razorpay_subscriptions()
    assert result["skipped"] == "razorpay_disabled"
    svc.db.execute.assert_not_called()


@pytest.mark.unit
def test_no_stale_subscriptions_is_a_noop():
    svc = _service_with_stale([])
    with patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True):
        result = svc.reconcile_razorpay_subscriptions()
    assert result == {"checked": 0, "flagged": 0}


@pytest.mark.unit
def test_remote_still_active_resyncs_period_without_downgrading():
    """A dropped webhook is not proof of non-payment — if Razorpay says the
    subscription is still active, resync the period locally and do not
    touch entitlements."""
    sub = _stale_sub()
    svc = _service_with_stale([sub])
    client = MagicMock()
    client.subscription.fetch.return_value = {
        "status": "active",
        "current_start": 1_700_000_000,
        "current_end": 1_702_678_400,
    }

    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch.object(svc, "_downgrade_to_free") as downgrade:
        result = svc.reconcile_razorpay_subscriptions()

    assert result == {"checked": 1, "flagged": 0}
    downgrade.assert_not_called()
    updated_sub, updated_data = svc.sub_repo.update.call_args[0]
    assert updated_sub is sub
    assert updated_data["status"] == SubscriptionStatus.ACTIVE
    assert updated_data["current_period_end"] is not None


@pytest.mark.unit
def test_remote_halted_downgrades_and_marks_unpaid():
    sub = _stale_sub(status=SubscriptionStatus.PAST_DUE)
    svc = _service_with_stale([sub])
    client = MagicMock()
    client.subscription.fetch.return_value = {"status": "halted"}

    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch.object(svc, "_downgrade_to_free") as downgrade:
        result = svc.reconcile_razorpay_subscriptions()

    assert result == {"checked": 1, "flagged": 1}
    downgrade.assert_called_once_with(sub.company_id)
    updated_sub, updated_data = svc.sub_repo.update.call_args[0]
    assert updated_data["status"] == SubscriptionStatus.UNPAID


@pytest.mark.unit
def test_remote_cancelled_downgrades_and_marks_cancelled():
    sub = _stale_sub()
    svc = _service_with_stale([sub])
    client = MagicMock()
    client.subscription.fetch.return_value = {"status": "cancelled"}

    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch.object(svc, "_downgrade_to_free") as downgrade:
        result = svc.reconcile_razorpay_subscriptions()

    assert result == {"checked": 1, "flagged": 1}
    downgrade.assert_called_once_with(sub.company_id)
    updated_sub, updated_data = svc.sub_repo.update.call_args[0]
    assert updated_data["status"] == SubscriptionStatus.CANCELLED


@pytest.mark.unit
def test_remote_pending_marks_past_due_without_downgrade():
    sub = _stale_sub()
    svc = _service_with_stale([sub])
    client = MagicMock()
    client.subscription.fetch.return_value = {"status": "pending"}

    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch.object(svc, "_downgrade_to_free") as downgrade:
        result = svc.reconcile_razorpay_subscriptions()

    assert result == {"checked": 1, "flagged": 0}
    downgrade.assert_not_called()
    updated_sub, updated_data = svc.sub_repo.update.call_args[0]
    assert updated_data["status"] == SubscriptionStatus.PAST_DUE


@pytest.mark.unit
def test_fetch_failure_is_skipped_not_crashed():
    sub = _stale_sub()
    svc = _service_with_stale([sub])
    client = MagicMock()
    client.subscription.fetch.side_effect = Exception("network error")

    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True):
        result = svc.reconcile_razorpay_subscriptions()

    assert result == {"checked": 1, "flagged": 0}
    svc.sub_repo.update.assert_not_called()
