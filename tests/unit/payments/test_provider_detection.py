"""Unit tests for billing provider detection (Stripe / Razorpay flags)."""
from __future__ import annotations

import pytest

from app.payments.provider_flags import (
    billing_providers_status,
    razorpay_enabled,
    stripe_enabled,
)


@pytest.mark.unit
def test_razorpay_enabled_when_flag_and_both_keys(monkeypatch):
    monkeypatch.setattr("app.payments.provider_flags.settings.BILLING_ENABLE_RAZORPAY", True)
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_ID", "rzp_live_abc")
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_SECRET", "secret_xyz")
    assert razorpay_enabled() is True
    status = billing_providers_status()
    assert status["razorpay"]["available"] is True
    assert status["razorpay"]["configured"] is True
    assert status["razorpay"]["flag_enabled"] is True
    assert status["razorpay"]["key_id"] == "rzp_live_abc"


@pytest.mark.unit
def test_razorpay_disabled_when_flag_false(monkeypatch):
    monkeypatch.setattr("app.payments.provider_flags.settings.BILLING_ENABLE_RAZORPAY", False)
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_ID", "rzp_live_abc")
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_SECRET", "secret_xyz")
    assert razorpay_enabled() is False
    status = billing_providers_status()
    assert status["razorpay"]["available"] is False
    assert status["razorpay"]["key_id"] is None


@pytest.mark.unit
def test_razorpay_disabled_when_secret_missing(monkeypatch):
    monkeypatch.setattr("app.payments.provider_flags.settings.BILLING_ENABLE_RAZORPAY", True)
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_ID", "rzp_live_abc")
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_SECRET", "")
    assert razorpay_enabled() is False
    assert billing_providers_status()["razorpay"]["configured"] is False


@pytest.mark.unit
def test_razorpay_flag_accepts_string_true(monkeypatch):
    monkeypatch.setattr("app.payments.provider_flags.settings.BILLING_ENABLE_RAZORPAY", "true")
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_ID", " rzp_test ")
    monkeypatch.setattr("app.payments.provider_flags.settings.RAZORPAY_KEY_SECRET", " secret ")
    assert razorpay_enabled() is True
    assert billing_providers_status()["razorpay"]["key_id"] == "rzp_test"


@pytest.mark.unit
def test_stripe_requires_secret_key(monkeypatch):
    monkeypatch.setattr("app.payments.provider_flags.settings.BILLING_ENABLE_STRIPE", True)
    monkeypatch.setattr("app.payments.provider_flags.settings.STRIPE_SECRET_KEY", "")
    assert stripe_enabled() is False
    monkeypatch.setattr("app.payments.provider_flags.settings.STRIPE_SECRET_KEY", "sk_live_x")
    assert stripe_enabled() is True
