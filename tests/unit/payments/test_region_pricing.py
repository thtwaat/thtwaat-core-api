"""Unit tests for region-based billing pricing."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.payments.region_pricing import (
    detect_billing_region,
    plan_currency_for_region,
    plan_price_for_region,
)


@pytest.mark.unit
def test_detect_region_from_company_india():
    region = detect_billing_region(company_country="India")
    assert region.region == "IN"
    assert region.currency == "INR"
    assert region.provider == "razorpay"
    assert region.source == "company"


@pytest.mark.unit
def test_detect_region_from_cf_header():
    region = detect_billing_region(headers={"CF-IPCountry": "US"})
    assert region.region == "INTL"
    assert region.currency == "USD"
    assert region.provider == "stripe"
    assert region.source == "header"


@pytest.mark.unit
def test_detect_region_from_accept_language_in():
    region = detect_billing_region(accept_language="hi-IN,hi;q=0.9")
    assert region.region == "IN"
    assert region.provider == "razorpay"
    assert region.source == "accept_language"


@pytest.mark.unit
def test_detect_region_default_international():
    region = detect_billing_region()
    assert region.region == "INTL"
    assert region.currency == "USD"
    assert region.provider == "stripe"
    assert region.source == "default"


@pytest.mark.unit
def test_plan_price_inr_and_usd():
    plan = SimpleNamespace(
        amount=Decimal("29"),
        yearly_amount=Decimal("290"),
        price_inr=Decimal("999"),
        price_usd=Decimal("29"),
        yearly_price_inr=Decimal("9990"),
        yearly_price_usd=Decimal("290"),
        is_custom_pricing=False,
        currency="USD",
    )
    india = detect_billing_region(company_country="IN")
    intl = detect_billing_region(company_country="US")
    assert plan_price_for_region(plan, india) == Decimal("999")
    assert plan_currency_for_region(plan, india) == "INR"
    assert plan_price_for_region(plan, intl) == Decimal("29")
    assert plan_currency_for_region(plan, intl) == "USD"
    assert plan_price_for_region(plan, india, interval="year") == Decimal("9990")


@pytest.mark.unit
def test_custom_pricing_returns_zero():
    plan = SimpleNamespace(
        amount=Decimal("0"),
        price_inr=None,
        price_usd=None,
        is_custom_pricing=True,
        currency="USD",
        yearly_amount=None,
        yearly_price_inr=None,
        yearly_price_usd=None,
    )
    region = detect_billing_region(company_country="IN")
    assert plan_price_for_region(plan, region) == Decimal("0")


@pytest.mark.unit
def test_canonical_plans_region_prices():
    from app.payments.plan_catalog import CANONICAL_PLANS

    by_name = {p["name"]: p for p in CANONICAL_PLANS}
    assert by_name["Starter"]["price_inr"] == Decimal("999")
    assert by_name["Starter"]["price_usd"] == Decimal("29")
    assert by_name["Pro"]["price_inr"] == Decimal("2999")
    assert by_name["Business"]["price_inr"] == Decimal("9999")
    assert by_name["Enterprise"]["is_custom_pricing"] is True
