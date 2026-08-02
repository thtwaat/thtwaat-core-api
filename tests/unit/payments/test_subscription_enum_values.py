"""PG enum must bind Python Enum.values (active), not names (ACTIVE)."""

from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.subscriptions.model import (
    Subscription,
    SubscriptionProvider,
    SubscriptionStatus,
)


def test_subscription_status_enum_uses_values_not_names():
    status_type = Subscription.__table__.c.status.type
    provider_type = Subscription.__table__.c.provider.type
    expected_status = [e.value for e in SubscriptionStatus]
    expected_provider = [e.value for e in SubscriptionProvider]
    assert status_type.values_callable(SubscriptionStatus) == expected_status
    assert provider_type.values_callable(SubscriptionProvider) == expected_provider
    assert "ACTIVE" not in expected_status
    assert "active" in expected_status


def test_invoice_status_enum_uses_values_not_names():
    status_type = Invoice.__table__.c.status.type
    expected = [e.value for e in InvoiceStatus]
    assert status_type.values_callable(InvoiceStatus) == expected
    assert "PAID" not in expected
    assert "paid" in expected
