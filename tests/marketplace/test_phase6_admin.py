"""Phase 6: marketplace registry admin list + RBAC."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"mkt6-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Marketplace Admin Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Admin",
            "last_name": "User",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id


def _enable_templates(db_session, company_id: str):
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)


def test_admin_list_includes_draft_and_archived(client, db_session):
    headers, company_id = _auth(client, role="admin")
    _enable_templates(db_session, company_id)
    seed_marketplace_templates(db_session)

    draft = client.post(
        "/api/v1/marketplace/templates",
        json={
            "slug": f"draft-{uuid.uuid4().hex[:6]}",
            "name": "Draft Prompt",
            "category": "writing",
            "kind": "prompt",
            "description": "hidden from public browse",
            "publish": False,
            "default_config": {"prompt": "Hi"},
        },
        headers=headers,
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]
    assert draft.json()["status"] == "draft"

    public = client.get("/api/v1/marketplace/templates", headers=headers)
    assert public.status_code == 200
    assert all(i["id"] != draft_id for i in public.json()["items"])

    admin_all = client.get("/api/v1/marketplace/admin/templates?status=all", headers=headers)
    assert admin_all.status_code == 200, admin_all.text
    ids = {i["id"] for i in admin_all.json()["items"]}
    assert draft_id in ids

    admin_draft = client.get("/api/v1/marketplace/admin/templates?status=draft", headers=headers)
    assert admin_draft.status_code == 200
    assert any(i["id"] == draft_id for i in admin_draft.json()["items"])
    assert all(i["status"] == "draft" for i in admin_draft.json()["items"])

    archived = client.delete(f"/api/v1/marketplace/templates/{draft_id}", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    admin_archived = client.get("/api/v1/marketplace/admin/templates?status=archived", headers=headers)
    assert admin_archived.status_code == 200
    assert any(i["id"] == draft_id for i in admin_archived.json()["items"])


def test_admin_list_forbidden_for_viewer(client, db_session):
    headers, company_id = _auth(client, role="viewer")
    _enable_templates(db_session, company_id)
    resp = client.get("/api/v1/marketplace/admin/templates", headers=headers)
    assert resp.status_code == 403
