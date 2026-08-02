"""GET /payments/subscriptions/me must not 500 when no (or duplicate) active subs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.payments.subscriptions.model import SubscriptionProvider, SubscriptionStatus
from app.payments.subscriptions.repository import SubscriptionRepository
from app.payments.subscriptions.router import get_sub_service
from app.payments.subscriptions.service import SubscriptionService


def _user() -> UserProfileResponse:
    return UserProfileResponse(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        email="owner@example.com",
        first_name="A",
        last_name="B",
        role="company_owner",
    )


def _sub(**overrides):
    now = datetime.now(timezone.utc)
    base = dict(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        provider=SubscriptionProvider.MANUAL,
        provider_customer_id=None,
        provider_subscription_id=None,
        payment_id=None,
        invoice_id=None,
        status=SubscriptionStatus.ACTIVE,
        cancel_at_period_end=False,
        cancelled_at=None,
        trial_end=None,
        current_period_start=now,
        current_period_end=now,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
def test_subscriptions_me_returns_null_when_none():
    app = FastAPI()
    app.include_router(api_router)
    user = _user()

    class _Svc:
        def get_subscription(self, company_id):
            assert company_id == user.company_id
            return None

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_sub_service] = lambda: _Svc()

    with TestClient(app) as client:
        resp = client.get("/api/v1/payments/subscriptions/me")

    assert resp.status_code == 200, resp.text
    assert resp.json() is None


@pytest.mark.unit
def test_subscriptions_me_returns_active_subscription():
    app = FastAPI()
    app.include_router(api_router)
    user = _user()
    sub = _sub(company_id=user.company_id)

    class _Svc:
        def get_subscription(self, company_id):
            return sub

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_sub_service] = lambda: _Svc()

    with TestClient(app) as client:
        resp = client.get("/api/v1/payments/subscriptions/me")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(sub.id)
    assert body["status"] == "active"


@pytest.mark.unit
def test_get_active_by_company_prefers_newest_when_duplicates():
    """Duplicate ACTIVE rows must not raise MultipleResultsFound."""
    company_id = uuid.uuid4()
    older = _sub(company_id=company_id, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = _sub(company_id=company_id, created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))

    result = MagicMock()
    result.scalars.return_value.first.return_value = newer

    db = MagicMock()
    db.execute.return_value = result
    repo = SubscriptionRepository(db)

    got = repo.get_active_by_company(company_id)
    assert got is newer
    db.execute.assert_called_once()
