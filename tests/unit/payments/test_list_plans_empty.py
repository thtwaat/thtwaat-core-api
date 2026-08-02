"""GET /payments/plans must return 200 [] when no active plans exist.

Regression for path shadowing: without a slash-exact list route,
GET /api/v1/payments/plans was captured by GET /payments/{payment_id}.
- No Authorization → 401 from HTTPBearer
- With Authorization → 422 (request validation) when \"plans\" fails UUID parse
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.payments.plans.router import get_plan_service


class _EmptyPlans:
    def list_plans(self, active_only: bool = True):
        return []


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_plan_service] = lambda: _EmptyPlans()
    return TestClient(app, raise_server_exceptions=False)


def test_list_plans_empty_no_slash_returns_200():
    with _client() as client:
        resp = client.get("/api/v1/payments/plans")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_plans_empty_with_trailing_slash_returns_200():
    with _client() as client:
        resp = client.get("/api/v1/payments/plans/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_plans_empty_with_authorization_returns_200_not_422():
    """Authenticated clients must not hit /payments/{payment_id} UUID validation."""
    with _client() as client:
        resp = client.get(
            "/api/v1/payments/plans",
            headers={"Authorization": "Bearer unused-for-public-plans"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    assert resp.status_code != 422
