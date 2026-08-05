"""THTWAAT Studio Phase 1 — CRUD, permissions, validation."""
from __future__ import annotations

import uuid

import pytest


def _auth(client, role: str = "company_owner"):
    company_slug = f"studio-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Studio Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"studio-{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123!"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Studio",
            "last_name": "User",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id


@pytest.mark.unit
def test_derive_title():
    from app.studio.service import derive_title

    assert derive_title("Create a CRM\nwith billing", None).startswith("Create a CRM")
    assert derive_title("x" * 100, None).endswith("...")
    assert derive_title("prompt text", "My Title") == "My Title"


def test_create_list_get_project(client):
    headers, company_id = _auth(client)
    create = client.post(
        "/api/v2/studio/projects",
        json={
            "prompt": "Create a Hospital Management SaaS with AI appointment booking"
        },
        headers=headers,
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["status"] == "draft"
    assert body["workspace_id"] == company_id
    assert "Hospital" in body["title"] or "hospital" in body["title"].lower() or body["title"]
    project_id = body["id"]

    listed = client.get("/api/v2/studio/projects", headers=headers)
    assert listed.status_code == 200, listed.text
    data = listed.json()
    assert data["total"] >= 1
    assert any(i["id"] == project_id for i in data["items"])

    got = client.get(f"/api/v2/studio/projects/{project_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["prompt"].startswith("Create a Hospital")


def test_create_validation_rejects_short_prompt(client):
    headers, _ = _auth(client)
    resp = client.post(
        "/api/v2/studio/projects",
        json={"prompt": "short"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_member_cannot_delete_owner_can(client):
    owner_headers, company_id = _auth(client, role="company_owner")
    create = client.post(
        "/api/v2/studio/projects",
        json={"prompt": "Create an inventory SaaS with warehouse and billing"},
        headers=owner_headers,
    )
    assert create.status_code == 201, create.text
    project_id = create.json()["id"]

    # Member in same workspace
    email = f"member-{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123!"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Mem",
            "last_name": "Ber",
            "role": "member",
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    denied = client.delete(f"/api/v2/studio/projects/{project_id}", headers=member_headers)
    assert denied.status_code == 403

    deleted = client.delete(f"/api/v2/studio/projects/{project_id}", headers=owner_headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/v2/studio/projects/{project_id}", headers=owner_headers)
    assert missing.status_code == 404


def test_unauthenticated_rejected(client):
    resp = client.get("/api/v2/studio/projects")
    assert resp.status_code in (401, 403)
