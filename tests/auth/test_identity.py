"""Identity / password-reset coverage (OTP email verification removed)."""
import uuid
from unittest import mock

import pytest

from app.auth.service import AuthService


@pytest.fixture
def test_user(client):
    uid = uuid.uuid4().hex[:6]
    email = f"identity_{uid}@example.com"

    resp = client.post(
        "/api/v1/companies/",
        json={
            "name": f"Test Company {uid}",
            "slug": f"test-company-{uid}",
        },
    )
    company_id = resp.json()["id"]

    client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword123",
            "company_id": company_id,
            "first_name": "Test",
            "last_name": "User",
            "role": "employee",
        },
    )
    return email


@pytest.mark.integration
def test_password_reset_link_and_login(client, test_user):
    captured: dict[str, str] = {}

    def _capture(self, recipient: str, reset_url: str) -> None:
        captured["reset_url"] = reset_url

    with mock.patch.object(AuthService, "_send_password_reset_email", _capture):
        resp = client.post("/api/v1/auth/forgot-password", json={"email": test_user})
        assert resp.status_code == 200

        token = captured["reset_url"].split("token=", 1)[1]
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "not-a-valid-token-xxxxxxxx", "new_password": "newsecurepassword456"},
        )
        assert resp.status_code == 400

        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "newsecurepassword456"},
        )
        assert resp.status_code == 200

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": test_user, "password": "securepassword123"},
        )
        assert resp.status_code == 401

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": test_user, "password": "newsecurepassword456"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
