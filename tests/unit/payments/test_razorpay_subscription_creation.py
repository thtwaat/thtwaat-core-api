"""SubscriptionService.create_razorpay_subscription: creates a real Razorpay
Subscription (not an Order), resolves plan/price/interval server-side only,
and persists provider_subscription_id immediately.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.payments.subscriptions.model import SubscriptionProvider, SubscriptionStatus
from app.payments.subscriptions.schema import RazorpaySubscriptionCheckoutRequest
from app.payments.subscriptions.service import SubscriptionService


def _company(company_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=company_id, name="Acme", slug="acme")


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
        razorpay_plan_id="plan_existing_month",
        razorpay_yearly_plan_id="plan_existing_year",
        is_active=True,
        is_custom_pricing=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service(company) -> SubscriptionService:
    svc = SubscriptionService(db=MagicMock())
    svc.sub_repo = MagicMock()
    svc.plan_repo = MagicMock()
    svc.invoice_repo = MagicMock()
    svc.company_repo = MagicMock()
    svc.company_repo.get_by_id.return_value = company
    return svc


def _request(**overrides) -> RazorpaySubscriptionCheckoutRequest:
    base = dict(
        plan_id=uuid.uuid4(),
        customer_name="Ada Lovelace",
        customer_email="ada@example.com",
    )
    base.update(overrides)
    return RazorpaySubscriptionCheckoutRequest(**base)


@pytest.fixture(autouse=True)
def _razorpay_config(monkeypatch):
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_ID", "rzp_test_id")
    monkeypatch.setattr("app.payments.subscriptions.service.settings.RAZORPAY_KEY_SECRET", "rzp_test_secret")
    monkeypatch.setattr(
        "app.payments.subscriptions.service.settings.RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_MONTHLY", 120
    )
    monkeypatch.setattr(
        "app.payments.subscriptions.service.settings.RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_YEARLY", 15
    )


def _patched_client(razorpay_sub_id: str = "sub_new_123"):
    client = MagicMock()
    client.subscription.create.return_value = {"id": razorpay_sub_id}
    return client


@pytest.mark.unit
def test_create_subscription_uses_server_side_plan_and_persists_provider_id():
    company_id = uuid.uuid4()
    company = _company(company_id)
    svc = _service(company)
    plan = _plan(id=uuid.UUID(int=1))

    svc.plan_repo.get_by_id.return_value = plan
    svc.sub_repo.get_active_by_company.return_value = None
    svc.sub_repo.get_incomplete_by_company.return_value = None
    created_sub = SimpleNamespace(id=uuid.uuid4())
    svc.sub_repo.create.return_value = created_sub

    client = _patched_client()
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch(
             "app.payments.subscriptions.service.resolve_region_for_company",
             return_value=SimpleNamespace(region="IN", currency="INR", country_code="IN"),
         ):
        result = svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id))

    assert result.razorpay_subscription_id == "sub_new_123"
    assert result.subscription_id == created_sub.id
    assert result.provider == "razorpay"

    create_kwargs = client.subscription.create.call_args.kwargs["data"]
    # Client never supplies price/interval for plan creation — only plan_id
    # (already resolved server-side) and count/notify bookkeeping fields.
    assert create_kwargs["plan_id"] == "plan_existing_month"
    assert create_kwargs["total_count"] == 120
    assert create_kwargs["notes"]["company_id"] == str(company_id)
    assert create_kwargs["notes"]["plan_id"] == str(plan.id)

    created_row = svc.sub_repo.create.call_args[0][0]
    assert created_row["provider"] == SubscriptionProvider.RAZORPAY
    assert created_row["provider_subscription_id"] == "sub_new_123"
    assert created_row["status"] == SubscriptionStatus.INCOMPLETE


@pytest.mark.unit
def test_yearly_interval_selects_yearly_plan_and_total_count():
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))
    plan = _plan(id=uuid.UUID(int=2))
    svc.plan_repo.get_by_id.return_value = plan
    svc.sub_repo.get_active_by_company.return_value = None
    svc.sub_repo.get_incomplete_by_company.return_value = None
    svc.sub_repo.create.return_value = SimpleNamespace(id=uuid.uuid4())

    client = _patched_client("sub_year_1")
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch(
             "app.payments.subscriptions.service.resolve_region_for_company",
             return_value=SimpleNamespace(region="IN", currency="INR", country_code="IN"),
         ):
        svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id, interval="year"))

    create_kwargs = client.subscription.create.call_args.kwargs["data"]
    assert create_kwargs["plan_id"] == "plan_existing_year"
    assert create_kwargs["total_count"] == 15
    assert create_kwargs["notes"]["interval"] == "year"


@pytest.mark.unit
def test_custom_pricing_plan_is_rejected():
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))
    plan = _plan(is_custom_pricing=True)
    svc.plan_repo.get_by_id.return_value = plan

    with patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True):
        with pytest.raises(HTTPException) as exc:
            svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id))

    assert exc.value.status_code == 400


@pytest.mark.unit
def test_inactive_plan_is_rejected():
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))
    plan = _plan(is_active=False)
    svc.plan_repo.get_by_id.return_value = plan

    with patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True):
        with pytest.raises(HTTPException) as exc:
            svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id))

    assert exc.value.status_code == 404


@pytest.mark.unit
def test_razorpay_disabled_returns_503():
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))

    with patch("app.payments.subscriptions.service.razorpay_enabled", return_value=False):
        with pytest.raises(HTTPException) as exc:
            svc.create_razorpay_subscription(company_id, _request())

    assert exc.value.status_code == 503


@pytest.mark.unit
def test_reuses_existing_incomplete_razorpay_row_instead_of_creating_new():
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))
    plan = _plan(id=uuid.UUID(int=3))
    svc.plan_repo.get_by_id.return_value = plan
    svc.sub_repo.get_active_by_company.return_value = None
    pending = SimpleNamespace(id=uuid.uuid4(), metadata_={"old": "value"})
    svc.sub_repo.get_incomplete_by_company.return_value = pending
    svc.sub_repo.update.return_value = pending

    client = _patched_client("sub_reuse_1")
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch(
             "app.payments.subscriptions.service.resolve_region_for_company",
             return_value=SimpleNamespace(region="IN", currency="INR", country_code="IN"),
         ):
        svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id))

    svc.sub_repo.create.assert_not_called()
    svc.sub_repo.update.assert_called_once()
    updated_sub, updated_data = svc.sub_repo.update.call_args[0]
    assert updated_sub is pending
    assert updated_data["provider_subscription_id"] == "sub_reuse_1"


@pytest.mark.unit
def test_conflict_when_active_recurring_razorpay_subscription_already_exists():
    """A live Razorpay Subscription (ACTIVE row with a real
    provider_subscription_id already set) must never be joined by a second
    one — that would orphan the first (still auto-charging on Razorpay's
    side, with no local record once its id is overwritten). The endpoint
    must refuse before ever calling Razorpay, so no second mandate is
    created remotely either."""
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))
    plan = _plan(id=uuid.UUID(int=5))
    svc.plan_repo.get_by_id.return_value = plan
    existing_live_sub = SimpleNamespace(
        id=uuid.uuid4(),
        provider=SubscriptionProvider.RAZORPAY,
        provider_subscription_id="sub_already_live",
        metadata_={},
    )
    svc.sub_repo.get_active_by_company.return_value = existing_live_sub

    client = _patched_client("sub_should_never_be_created")
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch(
             "app.payments.subscriptions.service.resolve_region_for_company",
             return_value=SimpleNamespace(region="IN", currency="INR", country_code="IN"),
         ):
        with pytest.raises(HTTPException) as exc:
            svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id))

    assert exc.value.status_code == 409
    client.subscription.create.assert_not_called()
    svc.sub_repo.update.assert_not_called()
    svc.sub_repo.create.assert_not_called()


@pytest.mark.unit
def test_legacy_one_time_active_row_does_not_block_new_subscription():
    """An ACTIVE Razorpay row from the legacy one-time Order flow has no
    provider_subscription_id — there is no live recurring mandate to orphan,
    so starting a real recurring subscription must proceed normally (and may
    reuse that row, matching existing behaviour)."""
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))
    plan = _plan(id=uuid.UUID(int=6))
    svc.plan_repo.get_by_id.return_value = plan
    legacy_one_time_sub = SimpleNamespace(
        id=uuid.uuid4(),
        provider=SubscriptionProvider.RAZORPAY,
        provider_subscription_id=None,
        metadata_={},
    )
    svc.sub_repo.get_active_by_company.return_value = legacy_one_time_sub
    svc.sub_repo.update.return_value = legacy_one_time_sub

    client = _patched_client("sub_new_recurring")
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch(
             "app.payments.subscriptions.service.resolve_region_for_company",
             return_value=SimpleNamespace(region="IN", currency="INR", country_code="IN"),
         ):
        result = svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id))

    client.subscription.create.assert_called_once()
    assert result.razorpay_subscription_id == "sub_new_recurring"
    svc.sub_repo.update.assert_called_once()
    updated_sub, updated_data = svc.sub_repo.update.call_args[0]
    assert updated_sub is legacy_one_time_sub
    assert updated_data["provider_subscription_id"] == "sub_new_recurring"


@pytest.mark.unit
def test_does_not_overwrite_active_non_razorpay_subscription_row():
    """An active Stripe subscription must never be clobbered by a Razorpay
    checkout attempt — a new row is created instead."""
    company_id = uuid.uuid4()
    svc = _service(_company(company_id))
    plan = _plan(id=uuid.UUID(int=4))
    svc.plan_repo.get_by_id.return_value = plan
    active_stripe_sub = SimpleNamespace(id=uuid.uuid4(), provider=SubscriptionProvider.STRIPE, metadata_={})
    svc.sub_repo.get_active_by_company.return_value = active_stripe_sub
    svc.sub_repo.get_incomplete_by_company.return_value = None
    svc.sub_repo.create.return_value = SimpleNamespace(id=uuid.uuid4())

    client = _patched_client("sub_no_clobber")
    with patch("razorpay.Client", return_value=client), \
         patch("app.payments.subscriptions.service.razorpay_enabled", return_value=True), \
         patch(
             "app.payments.subscriptions.service.resolve_region_for_company",
             return_value=SimpleNamespace(region="IN", currency="INR", country_code="IN"),
         ):
        svc.create_razorpay_subscription(company_id, _request(plan_id=plan.id))

    svc.sub_repo.update.assert_not_called()
    svc.sub_repo.create.assert_called_once()
