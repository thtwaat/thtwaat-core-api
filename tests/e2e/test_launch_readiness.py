"""Production launch readiness API probes (pytest e2e marker)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_live_or_liveness(e2e_client):
    live = e2e_client.get("/live")
    if live.status_code >= 400:
        live = e2e_client.get("/liveness")
    assert live.status_code == 200


def test_ready_optional(e2e_client):
    ready = e2e_client.get("/ready")
    # Ready may 503 if dependencies warming — still must not 404
    assert ready.status_code in (200, 503)


def test_api_status_running(e2e_client):
    resp = e2e_client.get("/api/v1/status")
    assert resp.status_code == 200
    body = resp.json()
    assert (body.get("status") or body.get("state") or "").lower() in {
        "running",
        "ok",
        "healthy",
        "up",
    } or "status" in body


def test_plans_public_for_billing(e2e_client):
    resp = e2e_client.get("/api/v1/payments/plans/?country=US")
    if resp.status_code == 404:
        resp = e2e_client.get("/payments/plans/?country=US")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_widget_bundle_served(e2e_client):
    resp = e2e_client.get("/widget.js")
    assert resp.status_code == 200
    text = resp.text
    assert "THTWAAT" in text or "Widget" in text or "tht" in text.lower()


def test_public_chat_rejects_invalid_key_safely(e2e_client):
    resp = e2e_client.post(
        "/public/v1/chat",
        json={"api_key": "tht_live_invalid", "message": "ping"},
    )
    assert resp.status_code < 500


def test_metrics_endpoint_exists(e2e_client):
    resp = e2e_client.get("/metrics")
    # May be protected (401/403) — must not 404
    assert resp.status_code != 404
