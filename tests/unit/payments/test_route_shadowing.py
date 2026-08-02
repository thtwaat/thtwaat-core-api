"""P0: static /payments/{plans,subscriptions,invoices} must not be shadowed by /{payment_id}."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.payments.invoices.router import get_invoice_service
from app.payments.model import Gateway, PaymentMethod, PaymentStatus
from app.payments.plans.router import get_plan_service
from app.payments.router import get_payment_service
from app.payments.schema import PaymentResponse
from app.payments.subscriptions.router import get_sub_service


def _billing_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)
    return app


def _user() -> UserProfileResponse:
    return UserProfileResponse(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        email=f"route-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Route",
        last_name="Test",
        role="company_owner",
    )


class _FakePlans:
    def list_plans(self, active_only: bool = True):
        return []


class _FakeSubs:
    def get_subscription(self, company_id):
        return None

    def list_subscriptions(self, company_id):
        return []


class _FakeInvoices:
    def list_invoices(self, company_id, skip: int = 0, limit: int = 50):
        return []


class _FakePayments:
    def get_payment(self, payment_id, company_id):
        now = datetime.now(timezone.utc)
        return PaymentResponse(
            id=payment_id,
            company_id=company_id,
            user_id=None,
            app_id=None,
            amount=1.0,
            currency="USD",
            payment_method=PaymentMethod.CARD,
            gateway=Gateway.MANUAL,
            gateway_transaction_id=None,
            invoice_number=None,
            status=PaymentStatus.PENDING,
            payment_metadata=None,
            paid_at=None,
            created_at=now,
            updated_at=now,
        )


@pytest.fixture
def client():
    app = _billing_app()
    user = _user()

    app.dependency_overrides[get_plan_service] = lambda: _FakePlans()
    app.dependency_overrides[get_sub_service] = lambda: _FakeSubs()
    app.dependency_overrides[get_invoice_service] = lambda: _FakeInvoices()
    app.dependency_overrides[get_payment_service] = lambda: _FakePayments()
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _path_keys(openapi: dict[str, Any]) -> set[str]:
    return {p.rstrip("/") for p in openapi["paths"]}


@pytest.mark.unit
def test_openapi_exposes_plans_subscriptions_invoices_and_payment_id():
    app = _billing_app()
    schema = app.openapi()
    paths = _path_keys(schema)

    assert "/api/v1/payments/plans" in paths
    assert "/api/v1/payments/subscriptions" in paths
    assert "/api/v1/payments/invoices" in paths
    assert "/api/v1/payments/{payment_id}" in paths

    def _get_op(path_suffix: str) -> dict[str, Any]:
        for key, value in schema["paths"].items():
            if key.rstrip("/") == path_suffix:
                return value
        raise AssertionError(f"missing OpenAPI path {path_suffix}")

    assert "get" in _get_op("/api/v1/payments/plans")
    assert _get_op("/api/v1/payments/plans")["get"].get("tags") == ["Plans"]
    assert "get" in _get_op("/api/v1/payments/subscriptions")
    assert _get_op("/api/v1/payments/subscriptions")["get"].get("tags") == ["Subscriptions"]
    assert "get" in _get_op("/api/v1/payments/invoices")
    assert _get_op("/api/v1/payments/invoices")["get"].get("tags") == ["Invoices"]
    assert "get" in _get_op("/api/v1/payments/{payment_id}")
    assert "Payments" in (_get_op("/api/v1/payments/{payment_id}")["get"].get("tags") or [])


@pytest.mark.unit
def test_get_payments_plans_not_shadowed(client: TestClient):
    resp = client.get("/api/v1/payments/plans")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.unit
def test_get_payments_subscriptions_not_shadowed(client: TestClient):
    resp = client.get("/api/v1/payments/subscriptions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.unit
def test_get_payments_invoices_not_shadowed(client: TestClient):
    resp = client.get("/api/v1/payments/invoices")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.unit
def test_get_payment_by_uuid_still_works(client: TestClient):
    payment_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/payments/{payment_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == payment_id


@pytest.mark.unit
def test_non_uuid_payment_path_is_not_treated_as_payment(client: TestClient):
    """Literal segments must not be coerced into /payments/{payment_id}."""
    resp = client.get("/api/v1/payments/not-a-uuid")
    assert resp.status_code == 404
