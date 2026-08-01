"""Integration tests for cross-tenant IDOR hardening (companies / users / apps)."""

from __future__ import annotations

import uuid

from app.rbac.enums import EnterpriseRole
from app.users.model import User


def _mk_company(client, prefix: str = "t") -> dict:
    slug = f"{prefix}-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Co {slug}", "slug": slug},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def _mk_owner(client, company_id: str, role: str = "company_owner") -> tuple[dict, str, str]:
    email = f"o-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Own",
            "last_name": "Er",
            "role": role,
        },
    )
    assert resp.status_code == 201, resp.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return headers, email, password


def _elevate_super_admin(db_session, email: str) -> None:
    row = db_session.query(User).filter(User.email == email).one()
    row.role = EnterpriseRole.SUPER_ADMIN
    db_session.commit()


# ── Companies ─────────────────────────────────────────────────────────────────

def test_companies_own_company_ok(client):
    co = _mk_company(client, "own")
    headers, _, _ = _mk_owner(client, co["id"])
    resp = client.get(f"/api/v1/companies/{co['id']}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == co["id"]

    patch = client.patch(
        f"/api/v1/companies/{co['id']}",
        headers=headers,
        json={"display_name": "Updated"},
    )
    assert patch.status_code == 200, patch.text


def test_companies_foreign_company_404(client):
    a = _mk_company(client, "a")
    b = _mk_company(client, "b")
    headers, _, _ = _mk_owner(client, a["id"])
    resp = client.get(f"/api/v1/companies/{b['id']}", headers=headers)
    assert resp.status_code == 404, resp.text

    patch = client.patch(
        f"/api/v1/companies/{b['id']}",
        headers=headers,
        json={"display_name": "Nope"},
    )
    assert patch.status_code == 404, patch.text

    listing = client.get("/api/v1/companies/", headers=headers)
    assert listing.status_code == 403, listing.text


def test_companies_platform_admin_ok(client, db_session):
    a = _mk_company(client, "pa")
    b = _mk_company(client, "pb")
    headers, email, _ = _mk_owner(client, a["id"])
    _elevate_super_admin(db_session, email)
    # refresh token after role change
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.get(f"/api/v1/companies/{b['id']}", headers=headers)
    assert resp.status_code == 200, resp.text

    listing = client.get("/api/v1/companies/", headers=headers)
    assert listing.status_code == 200, listing.text


# ── Users ─────────────────────────────────────────────────────────────────────

def test_users_own_company_ok(client):
    co = _mk_company(client, "uo")
    headers, _, _ = _mk_owner(client, co["id"])
    # create peer in same company
    peer = client.post(
        "/api/v1/users/",
        json={
            "email": f"peer-{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword",
            "company_id": co["id"],
            "first_name": "Peer",
            "last_name": "User",
            "role": "employee",
        },
    )
    assert peer.status_code == 201, peer.text
    peer_id = peer.json()["id"]

    listing = client.get("/api/v1/users/", headers=headers)
    assert listing.status_code == 200, listing.text
    ids = {u["id"] for u in listing.json()["results"]}
    assert peer_id in ids

    got = client.get(f"/api/v1/users/{peer_id}", headers=headers)
    assert got.status_code == 200, got.text


def test_users_foreign_company_404(client):
    a = _mk_company(client, "ua")
    b = _mk_company(client, "ub")
    headers_a, _, _ = _mk_owner(client, a["id"])
    foreign = client.post(
        "/api/v1/users/",
        json={
            "email": f"fx-{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword",
            "company_id": b["id"],
            "first_name": "Fx",
            "last_name": "User",
            "role": "employee",
        },
    )
    assert foreign.status_code == 201, foreign.text
    foreign_id = foreign.json()["id"]

    got = client.get(f"/api/v1/users/{foreign_id}", headers=headers_a)
    assert got.status_code == 404, got.text

    listing = client.get(
        f"/api/v1/users/?company_id={b['id']}",
        headers=headers_a,
    )
    assert listing.status_code == 404, listing.text


# ── Apps ──────────────────────────────────────────────────────────────────────

def test_apps_create_ignores_payload_company_id(client):
    a = _mk_company(client, "aa")
    b = _mk_company(client, "ab")
    headers, _, _ = _mk_owner(client, a["id"])

    resp = client.post(
        "/api/v1/apps/",
        headers=headers,
        json={
            "name": "My App",
            "slug": f"app-{uuid.uuid4().hex[:6]}",
            "company_id": b["id"],  # foreign — must be ignored
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["company_id"] == a["id"]
    # create still returns raw key
    assert resp.json()["api_key"].startswith("thtwaat_live_")


def test_apps_foreign_app_404(client):
    a = _mk_company(client, "fa")
    b = _mk_company(client, "fb")
    headers_a, _, _ = _mk_owner(client, a["id"])
    headers_b, _, _ = _mk_owner(client, b["id"])

    created = client.post(
        "/api/v1/apps/",
        headers=headers_b,
        json={
            "name": "B App",
            "slug": f"bapp-{uuid.uuid4().hex[:6]}",
            "company_id": b["id"],
        },
    )
    assert created.status_code == 201, created.text
    app_id = created.json()["id"]

    got = client.get(f"/api/v1/apps/{app_id}", headers=headers_a)
    assert got.status_code == 404, got.text

    listing = client.get("/api/v1/apps/", headers=headers_a)
    assert listing.status_code == 200, listing.text
    assert all(item["company_id"] == a["id"] for item in listing.json()["results"])
    # list keys are masked
    for item in listing.json()["results"]:
        assert "…" in item["api_key"] or item["api_key"] == "***"


def test_apps_platform_admin_ok(client, db_session):
    a = _mk_company(client, "apa")
    b = _mk_company(client, "apb")
    headers, email, _ = _mk_owner(client, a["id"])
    _elevate_super_admin(db_session, email)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post(
        "/api/v1/apps/",
        headers=headers,
        json={
            "name": "Admin App",
            "slug": f"adm-{uuid.uuid4().hex[:6]}",
            "company_id": b["id"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["company_id"] == b["id"]

    got = client.get(f"/api/v1/apps/{created.json()['id']}", headers=headers)
    assert got.status_code == 200, got.text
