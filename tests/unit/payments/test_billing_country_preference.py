"""Persistence helpers for selectable billing country."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.payments.billing_region import (
    BILLING_COUNTRY_SETTING_KEY,
    region_payload,
    resolve_region_for_company,
    save_billing_country_preference,
)
from app.payments.region_pricing import BillingRegion


@pytest.mark.unit
def test_region_payload_shape():
    region = BillingRegion("IN", "INR", "razorpay", "IN", "user")
    payload = region_payload(region)
    assert payload["country"] == "IN"
    assert payload["currency"] == "INR"
    assert payload["gateway"] == "razorpay"
    assert payload["region"] == "IN"
    assert payload["provider"] == "razorpay"


@pytest.mark.unit
def test_resolve_uses_explicit_country_over_preference():
    company = SimpleNamespace(country="US", settings={BILLING_COUNTRY_SETTING_KEY: "IN"})
    db = MagicMock()
    db.get.return_value = company
    region = resolve_region_for_company(db, uuid4(), country="GB")
    assert region.region == "INTL"
    assert region.country_code == "GB"
    assert region.source == "user"
    assert region.provider == "stripe"


@pytest.mark.unit
def test_resolve_uses_saved_preference():
    company = SimpleNamespace(country="US", settings={BILLING_COUNTRY_SETTING_KEY: "IN"})
    db = MagicMock()
    db.get.return_value = company
    region = resolve_region_for_company(db, uuid4())
    assert region.region == "IN"
    assert region.source == "preference"


@pytest.mark.unit
def test_save_billing_country_preference():
    company = SimpleNamespace(country=None, settings={})
    db = MagicMock()
    db.get.return_value = company
    payload = save_billing_country_preference(db, uuid4(), "in")
    assert company.settings[BILLING_COUNTRY_SETTING_KEY] == "IN"
    assert company.country == "IN"
    assert payload["country"] == "IN"
    assert payload["currency"] == "INR"
    assert payload["gateway"] == "razorpay"
    db.commit.assert_called_once()


@pytest.mark.unit
def test_save_billing_country_invalid():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(country="US", settings={})
    with pytest.raises(HTTPException) as exc:
        save_billing_country_preference(db, uuid4(), " ")
    assert exc.value.status_code == 400
