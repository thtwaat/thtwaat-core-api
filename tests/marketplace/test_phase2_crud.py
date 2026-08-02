"""Phase 2 marketplace CRUD: pagination, sort, PUT/DELETE, install aliases."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"mkt2-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Marketplace Co 2", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Owner",
            "last_name": "User",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id


def _enable_templates(db_session, company_id: str):
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)


def test_list_templates_paginated_and_sorted(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id)
    seed_marketplace_templates(db_session)

    page = client.get(
        "/api/v1/marketplace/templates?limit=2&offset=0&sort=name",
        headers=headers,
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert body["sort"] == "name"
    assert body["total"] >= 3
    assert len(body["items"]) == 2
    names = [i["name"] for i in body["items"]]
    assert names == sorted(names)

    page2 = client.get(
        "/api/v1/marketplace/templates?limit=2&offset=2&sort=name",
        headers=headers,
    )
    assert page2.status_code == 200
    assert page2.json()["offset"] == 2
    assert len(page2.json()["items"]) >= 1


def test_crud_put_and_soft_delete(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id)

    created = client.post(
        "/api/v1/marketplace/templates",
        json={
            "slug": f"phase2-{uuid.uuid4().hex[:6]}",
            "name": "Phase2 Prompt",
            "category": "writing",
            "kind": "prompt",
            "pricing_tier": "free",
            "description": "test",
            "publish": True,
            "default_config": {"prompt": "Hello {{name}}", "temperature": 0.2},
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert created.json()["kind"] == "prompt"

    put = client.put(
        f"/api/v1/marketplace/templates/{tid}",
        json={"name": "Phase2 Prompt Updated", "pricing_tier": "starter"},
        headers=headers,
    )
    assert put.status_code == 200, put.text
    assert put.json()["name"] == "Phase2 Prompt Updated"
    assert put.json()["pricing_tier"] == "starter"

    deleted = client.delete(f"/api/v1/marketplace/templates/{tid}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "archived"
    assert deleted.json()["is_public"] is False

    # Archived templates drop out of public browse
    listed = client.get("/api/v1/marketplace/templates", headers=headers)
    assert listed.status_code == 200
    assert all(i["id"] != tid for i in listed.json()["items"])


def test_install_update_uninstall_aliases(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id)
    seed_marketplace_templates(db_session)

    install = client.post(
        "/api/v1/marketplace/templates/ai-website-starter/install",
        json={"create_api_key": False},
        headers=headers,
    )
    assert install.status_code == 201, install.text
    install_id = install.json()["id"]

    detail = client.get("/api/v1/marketplace/templates/ai-website-starter", headers=headers)
    template_id = detail.json()["id"]
    client.post(
        f"/api/v1/marketplace/templates/{template_id}/versions",
        json={"version": "1.0.1", "changelog": "patch", "config": {}, "set_latest": True},
        headers=headers,
    )

    updated = client.post(
        "/api/v1/marketplace/templates/update",
        json={"installation_id": install_id, "version": "1.0.1"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["installed_version"] == "1.0.1"

    removed = client.post(
        "/api/v1/marketplace/templates/uninstall",
        json={"installation_id": install_id},
        headers=headers,
    )
    assert removed.status_code == 200, removed.text


def test_viewer_cannot_manage_templates(client, db_session):
    headers, company_id = _auth(client, role="viewer")
    _enable_templates(db_session, company_id)
    seed_marketplace_templates(db_session)

    browse = client.get("/api/v1/marketplace/templates", headers=headers)
    assert browse.status_code == 200

    create = client.post(
        "/api/v1/marketplace/templates",
        json={
            "slug": "nope-viewer",
            "name": "Nope",
            "category": "saas",
            "publish": True,
        },
        headers=headers,
    )
    assert create.status_code in (401, 403)
