"""Billing admin analytics helpers for Super Admin dashboard."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.payments.admin_router import admin_billing_analytics
from app.payments.subscriptions.model import SubscriptionStatus


@pytest.mark.unit
def test_admin_billing_analytics_shape():
    db = MagicMock()
    plan = SimpleNamespace(id="p1", name="Starter", amount=Decimal("29"), interval="month")
    sub = SimpleNamespace(plan_id="p1", status=SubscriptionStatus.ACTIVE, company_id="c1")

    db.query.return_value.filter.return_value.all.return_value = [sub]
    db.get.return_value = plan
    # paid sum, refunds path, top customers query chain
    db.query.return_value.filter.return_value.scalar.return_value = Decimal("100")
    db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.count.return_value = 0

    meter_q = MagicMock()
    meter_q.filter.return_value.scalar.return_value = Decimal("5")
    # Fallback path when Payment model import works or fails — function catches Exception

    with patch("app.payments.admin_router.billing_providers_status", return_value={"stripe": {"available": True}}):
        # Call underlying logic by invoking with mocked db dependency manually
        result = admin_billing_analytics(_=SimpleNamespace(role="super_admin"), db=db)

    assert "mrr" in result
    assert "revenue" in result
    assert "failed_payments" in result
    assert "ai_costs" in result
    assert result["mrr"] == 29.0
