"""Phase 6 enterprise billing unit tests."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.payments.billing_extras import apply_coupon_discount
from app.payments.provider_flags import billing_providers_status, razorpay_enabled, stripe_enabled
from app.payments.plan_catalog import CANONICAL_PLANS


@pytest.mark.unit
def test_canonical_plans_cover_five_tiers():
    names = {p["name"] for p in CANONICAL_PLANS}
    assert names == {"Free", "Starter", "Pro", "Business", "Enterprise"}
    free = next(p for p in CANONICAL_PLANS if p["name"] == "Free")
    assert Decimal(str(free["amount"])) == Decimal("0")
    assert free["max_tokens"] > 0


@pytest.mark.unit
def test_coupon_percent_and_amount_discount():
    percent = MagicMock(percent_off=Decimal("20"), amount_off=None)
    assert apply_coupon_discount(Decimal("100"), percent) == Decimal("80.00")

    fixed = MagicMock(percent_off=None, amount_off=Decimal("10"))
    assert apply_coupon_discount(Decimal("25"), fixed) == Decimal("15.00")


@pytest.mark.unit
def test_provider_flags_respect_settings(monkeypatch):
    monkeypatch.setattr("app.payments.provider_flags.settings.BILLING_ENABLE_STRIPE", True, raising=False)
    monkeypatch.setattr("app.payments.provider_flags.settings.STRIPE_SECRET_KEY", "sk_test", raising=False)
    monkeypatch.setattr("app.payments.provider_flags.settings.BILLING_ENABLE_RAZORPAY", False, raising=False)
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_ID", "rzp", raising=False)
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_SECRET", "secret", raising=False)
    assert stripe_enabled() is True
    assert razorpay_enabled() is False
    status = billing_providers_status()
    assert status["stripe"]["available"] is True
    assert status["razorpay"]["available"] is False
    assert status["razorpay"].get("key_id") is None


@pytest.mark.unit
def test_claim_webhook_event_idempotent():
    from app.payments import billing_extras as be

    db = MagicMock()
    existing = MagicMock()
    existing.processed = True
    db.query.return_value.filter.return_value.first.return_value = existing
    second = be.claim_webhook_event(
        db, provider="stripe", event_id="evt_1", event_type="invoice.paid", payload={}
    )
    assert second is None


@pytest.mark.unit
def test_plan_create_allows_zero_amount():
    from app.payments.plans.schema import PlanCreate

    plan = PlanCreate(name="Free", amount=Decimal("0"))
    assert plan.amount == Decimal("0")
    assert plan.max_workspaces == 1
