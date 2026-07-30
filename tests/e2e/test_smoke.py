"""End-to-end smoke against a deployed stack."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_liveness(e2e_client):
    resp = e2e_client.get("/liveness")
    assert resp.status_code == 200


def test_api_status(e2e_client):
    resp = e2e_client.get("/api/v1/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "running"
