"""Public-launch auth: email login, Google OAuth, link-based password reset."""
from __future__ import annotations

import uuid
from unittest import mock

import pytest

from app.auth.service import AuthService


def _create_user(client, email: str | None = None, password: str = "securepassword123") -> tuple[str, str]:
    uid = uuid.uuid4().hex[:6]
    email = email or f"launch_{uid}@example.com"
    company = client.post(
        "/api/v1/companies/",
        json={
            "name": f"Launch Co {uid}",
            "slug": f"launch-co-{uid}",
        },
    )
    assert company.status_code in (200, 201), company.text
    company_id = company.json()["id"]
    user = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Launch",
            "last_name": "User",
            "role": "employee",
        },
    )
    assert user.status_code in (200, 201), user.text
    return email, password


@pytest.mark.integration
def test_email_password_login_success(client):
    email, password = _create_user(client)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("access_token")
    assert body.get("refresh_token")


@pytest.mark.integration
def test_email_password_login_rejects_bad_password(client):
    email, _ = _create_user(client)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert resp.status_code == 401


@pytest.mark.integration
def test_google_login_creates_account_and_workspace(client):
    email = f"google_{uuid.uuid4().hex[:8]}@example.com"

    async def _fake_verify(_token: str):
        return {
            "email": email,
            "email_verified": "true",
            "given_name": "Gita",
            "family_name": "User",
            "sub": "google-sub-1",
            "aud": "test-client",
        }

    with mock.patch("app.auth.google_oauth.google_oauth_configured", return_value=True), mock.patch(
        "app.auth.google_oauth.require_google_oauth_configured", return_value=None
    ), mock.patch(
        "app.auth.google_oauth.verify_google_id_token",
        side_effect=_fake_verify,
    ):
        resp = client.post("/api/v1/auth/google", json={"id_token": "fake.google.token"})
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    assert tokens.get("access_token")

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == email

    with mock.patch("app.auth.google_oauth.google_oauth_configured", return_value=True), mock.patch(
        "app.auth.google_oauth.require_google_oauth_configured", return_value=None
    ), mock.patch(
        "app.auth.google_oauth.verify_google_id_token",
        side_effect=_fake_verify,
    ):
        again = client.post("/api/v1/auth/google", json={"id_token": "fake.google.token"})
    assert again.status_code == 200
    me2 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {again.json()['access_token']}"},
    )
    assert me2.json()["email"] == email
    assert me2.json()["id"] == me.json()["id"]


@pytest.mark.integration
def test_password_reset_link_flow(client):
    email, password = _create_user(client)
    captured: dict[str, str] = {}

    def _capture_email(self, recipient: str, reset_url: str) -> None:
        captured["recipient"] = recipient
        captured["reset_url"] = reset_url

    with mock.patch.object(AuthService, "_send_password_reset_email", _capture_email):
        forgot = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200, forgot.text
    assert "reset link" in forgot.json()["detail"].lower()
    assert email in captured.get("recipient", "")
    assert "token=" in captured.get("reset_url", "")
    token = captured["reset_url"].split("token=", 1)[1]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "brandnewpassword99"},
    )
    assert reset.status_code == 200, reset.text

    old = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert old.status_code == 401

    new = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "brandnewpassword99"},
    )
    assert new.status_code == 200, new.text

    reuse = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "anotherpassword99"},
    )
    assert reuse.status_code == 400

    unknown = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": f"missing_{uuid.uuid4().hex[:6]}@example.com"},
    )
    assert unknown.status_code == 200


@pytest.mark.integration
def test_otp_routes_removed(client):
    assert client.post("/api/v1/auth/send-otp", json={"purpose": "LOGIN", "email": "a@b.com"}).status_code == 404
    assert client.post(
        "/api/v1/auth/verify-otp", json={"purpose": "LOGIN", "email": "a@b.com", "code": "123456"}
    ).status_code == 404
    assert client.post("/api/v1/auth/resend-otp", json={"purpose": "LOGIN", "email": "a@b.com"}).status_code == 404
    assert client.post("/api/v1/auth/send-email-verification", json={"email": "a@b.com"}).status_code == 404
