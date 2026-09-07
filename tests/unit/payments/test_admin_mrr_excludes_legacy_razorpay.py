"""Admin billing analytics must not count a legacy one-time Razorpay
subscription (no provider_subscription_id, or a lapsed/absent period) toward
MRR/ARR — only a real recurring Razorpay subscription with a live period
counts. Stripe/manual subscriptions are unaffected.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.payments.admin_router import admin_billing_analytics
from app.payments.subscriptions.model import SubscriptionProvider, SubscriptionStatus


def _plan(plan_id, amount="29", interval="month"):
    return SimpleNamespace(id=plan_id, name="Starter", amount=Decimal(amount), interval=interval)


def _run_analytics(subs, plans_by_id):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = subs
    db.get.side_effect = lambda _model, plan_id: plans_by_id.get(plan_id)
    db.query.return_value.filter.return_value.scalar.return_value = Decimal("0")
    db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.count.return_value = 0

    with patch("app.payments.admin_router.billing_providers_status", return_value={"stripe": {"available": True}}):
        return admin_billing_analytics(_=SimpleNamespace(role="super_admin"), db=db)


@pytest.mark.unit
def test_legacy_one_time_razorpay_sub_excluded_from_mrr():
    plan = _plan("p1")
    legacy_sub = SimpleNamespace(
        plan_id="p1",
        status=SubscriptionStatus.ACTIVE,
        company_id="c1",
        provider=SubscriptionProvider.RAZORPAY,
        provider_subscription_id=None,  # never set by the old order+verify flow
        current_period_end=None,
    )

    result = _run_analytics([legacy_sub], {"p1": plan})

    assert result["mrr"] == 0.0
    assert result["arr"] == 0.0
    assert result["legacy_one_time_razorpay_subscriptions"] == 1
    assert result["recurring_subscriptions"] == 0
    assert result["active_subscriptions"] == 1  # still counted as "active" overall


@pytest.mark.unit
def test_razorpay_sub_with_expired_period_excluded_even_if_provider_id_set():
    """A real recurring subscription whose period lapsed (reconciliation
    hasn't caught up yet, or webhooks stopped) must not inflate MRR either —
    it is only counted while its period is actually live."""
    plan = _plan("p1")
    expired_sub = SimpleNamespace(
        plan_id="p1",
        status=SubscriptionStatus.ACTIVE,
        company_id="c1",
        provider=SubscriptionProvider.RAZORPAY,
        provider_subscription_id="sub_real_1",
        current_period_end=datetime.now(timezone.utc) - timedelta(days=2),
    )

    result = _run_analytics([expired_sub], {"p1": plan})

    assert result["mrr"] == 0.0
    assert result["legacy_one_time_razorpay_subscriptions"] == 1


@pytest.mark.unit
def test_real_recurring_razorpay_subscription_counts_toward_mrr():
    plan = _plan("p1", amount="29", interval="month")
    live_sub = SimpleNamespace(
        plan_id="p1",
        status=SubscriptionStatus.ACTIVE,
        company_id="c1",
        provider=SubscriptionProvider.RAZORPAY,
        provider_subscription_id="sub_real_1",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
    )

    result = _run_analytics([live_sub], {"p1": plan})

    assert result["mrr"] == 29.0
    assert result["legacy_one_time_razorpay_subscriptions"] == 0
    assert result["recurring_subscriptions"] == 1


@pytest.mark.unit
def test_stripe_subscription_counts_toward_mrr_without_period_requirement():
    """Stripe reporting is unchanged by this Razorpay-specific fix."""
    plan = _plan("p1", amount="49", interval="month")
    stripe_sub = SimpleNamespace(
        plan_id="p1",
        status=SubscriptionStatus.ACTIVE,
        company_id="c1",
        provider=SubscriptionProvider.STRIPE,
        provider_subscription_id="sub_stripe_1",
        current_period_end=None,
    )

    result = _run_analytics([stripe_sub], {"p1": plan})

    assert result["mrr"] == 49.0
    assert result["legacy_one_time_razorpay_subscriptions"] == 0
