"""Integration tests: public signup role hardening + platform-admin bypass."""

import uuid

import pytest

from app.rbac.enums import EnterpriseRole
from app.users.model import User


def _company(client) -> str:
    slug = f"su-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/companies/", json={"name": "Signup Co", "slug": slug})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _user_payload(company_id: str, role: str | None = None) -> dict:
    body = {
        "email": f"u-{uuid.uuid4().hex[:8]}@example.com",
        "password": "securepassword",
        "company_id": company_id,
        "first_name": "Test",
        "last_name": "User",
    }
    if role is not None:
        body["role"] = role
    return body


def test_signup_without_role_defaults_to_employee(client):
    company_id = _company(client)
    payload = _user_payload(company_id)
    assert "role" not in payload
    resp = client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == EnterpriseRole.EMPLOYEE.value


def test_signup_with_company_owner(client):
    company_id = _company(client)
    resp = client.post("/api/v1/users/", json=_user_payload(company_id, "company_owner"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "company_owner"


def test_signup_with_employee(client):
    company_id = _company(client)
    resp = client.post("/api/v1/users/", json=_user_payload(company_id, "employee"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "employee"


def test_signup_requesting_super_admin_rejected(client):
    company_id = _company(client)
    resp = client.post("/api/v1/users/", json=_user_payload(company_id, "super_admin"))
    assert resp.status_code == 403, resp.text
    assert "super_admin" in resp.text.lower() or "not allowed" in resp.text.lower()


def test_signup_requesting_admin_rejected(client):
    company_id = _company(client)
    resp = client.post("/api/v1/users/", json=_user_payload(company_id, "admin"))
    assert resp.status_code == 403, resp.text


def test_authenticated_platform_admin_can_create_super_admin(client, db_session):
    company_id = _company(client)
    email = f"padmin-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"

    # Bootstrap a normal owner via public signup, then elevate in DB.
    create = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Plat",
            "last_name": "Admin",
            "role": "company_owner",
        },
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]

    row = db_session.query(User).filter(User.id == user_id).one()
    row.role = EnterpriseRole.SUPER_ADMIN
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    target_email = f"sa-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "email": target_email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Super",
            "last_name": "Admin",
            "role": "super_admin",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "super_admin"
    assert resp.json()["email"] == target_email
