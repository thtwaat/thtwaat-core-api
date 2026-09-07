"""SubscriptionService._ensure_razorpay_plan: creates/maps a Razorpay Plan id
for a monthly or yearly interval from our own Plan record only, and never
creates a duplicate once an id is already recorded.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.payments.region_pricing import BillingRegion
from app.payments.subscriptions.service import SubscriptionService


IN_REGION = BillingRegion("IN", "INR", "razorpay", "IN", "test")


def _plan(**overrides) -> SimpleNamespace:
    base = dict(
        id=uuid.uuid4(),
        name="Starter",
        description="Starter plan",
        amount=Decimal("999.00"),
        currency="INR",
        interval="month",
        interval_count=1,
        price_inr=Decimal("999.00"),
        yearly_price_inr=Decimal("9990.00"),
        razorpay_plan_id=None,
        razorpay_yearly_plan_id=None,
        is_custom_pricing=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service() -> SubscriptionService:
    svc = SubscriptionService(db=MagicMock())
    svc.plan_repo = MagicMock()
    return svc


@pytest.mark.unit
def test_creates_monthly_plan_from_server_side_amount_when_missing():
    svc = _service()
    plan = _plan()
    client = MagicMock()
    client.plan.create.return_value = {"id": "plan_month_new"}

    result = svc._ensure_razorpay_plan(client, plan, use_yearly=False, billing_region=IN_REGION)

    assert result == "plan_month_new"
    created_payload = client.plan.create.call_args.kwargs["data"]
    assert created_payload["period"] == "monthly"
    assert created_payload["item"]["amount"] == 99900  # server-side price_inr, in paise
    assert created_payload["item"]["currency"] == "INR"
    svc.plan_repo.update.assert_called_once_with(plan, {"razorpay_plan_id": "plan_month_new"})


@pytest.mark.unit
def test_creates_yearly_plan_using_yearly_field_and_price():
    svc = _service()
    plan = _plan()
    client = MagicMock()
    client.plan.create.return_value = {"id": "plan_year_new"}

    result = svc._ensure_razorpay_plan(client, plan, use_yearly=True, billing_region=IN_REGION)

    assert result == "plan_year_new"
    created_payload = client.plan.create.call_args.kwargs["data"]
    assert created_payload["period"] == "yearly"
    assert created_payload["item"]["amount"] == 999000  # yearly_price_inr, in paise
    svc.plan_repo.update.assert_called_once_with(plan, {"razorpay_yearly_plan_id": "plan_year_new"})


@pytest.mark.unit
def test_never_creates_duplicate_when_id_already_recorded():
    svc = _service()
    plan = _plan(razorpay_plan_id="plan_existing_123")
    client = MagicMock()

    result = svc._ensure_razorpay_plan(client, plan, use_yearly=False, billing_region=IN_REGION)

    assert result == "plan_existing_123"
    client.plan.create.assert_not_called()
    svc.plan_repo.update.assert_not_called()


@pytest.mark.unit
def test_concurrent_creation_keeps_first_persisted_id():
    """A concurrent request may have written razorpay_plan_id while this
    call was talking to Razorpay — db.refresh() picking that up must win
    over the id this call just created, so we never overwrite it."""
    svc = _service()
    plan = _plan()
    client = MagicMock()
    client.plan.create.return_value = {"id": "plan_from_this_call"}

    def _refresh(obj):
        # Simulate the concurrent writer landing between the first refresh
        # (sees nothing) and the second refresh (sees the winner) by only
        # mutating after plan.create() has already been called once.
        if client.plan.create.called:
            plan.razorpay_plan_id = "plan_from_other_request"

    svc.db.refresh.side_effect = _refresh

    result = svc._ensure_razorpay_plan(client, plan, use_yearly=False, billing_region=IN_REGION)

    assert result == "plan_from_other_request"
    svc.plan_repo.update.assert_not_called()


@pytest.mark.unit
def test_rejects_zero_amount_plan():
    svc = _service()
    plan = _plan(price_inr=Decimal("0"), amount=Decimal("0"))
    client = MagicMock()

    with pytest.raises(HTTPException) as exc:
        svc._ensure_razorpay_plan(client, plan, use_yearly=False, billing_region=IN_REGION)

    assert exc.value.status_code == 400
    client.plan.create.assert_not_called()
