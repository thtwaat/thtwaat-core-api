"""Phase 8: template versioning and release notes management."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"mkt8-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Versioning Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]
    email = f"ver-{uuid.uuid4().hex[:8]}@example.com"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Ver",
            "last_name": "User",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    assert login_resp.status_code == 200, login_resp.text
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}, company_id


def test_version_release_notes_update_promote_and_slug_list(client, db_session):
    headers, company_id = _auth(client)
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    seed_marketplace_templates(db_session)

    created = client.post(
        "/api/v1/marketplace/templates",
        json={
            "slug": f"rel-{uuid.uuid4().hex[:6]}",
            "name": "Release Notes Demo",
            "category": "writing",
            "kind": "prompt",
            "description": "versioning fixture",
            "publish": True,
            "version": "1.0.0",
            "changelog": "Initial",
            "default_config": {"prompt": "v1"},
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    slug = created.json()["slug"]

    v2 = client.post(
        f"/api/v1/marketplace/templates/{tid}/versions",
        json={
            "version": "1.1.0",
            "release_notes": "- Added better outlines\n- Fixed typos",
            "set_latest": False,
            "config": {"prompt": "v1.1"},
        },
        headers=headers,
    )
    assert v2.status_code == 201, v2.text
    assert v2.json()["is_latest"] is False
    assert v2.json()["release_notes"].startswith("- Added")
    assert v2.json()["changelog"].startswith("- Added")

    patch = client.patch(
        f"/api/v1/marketplace/templates/{slug}/versions/1.1.0",
        json={"release_notes": "- Added better outlines\n- Fixed typos\n- Docs"},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    assert "Docs" in patch.json()["release_notes"]

    promote = client.post(
        f"/api/v1/marketplace/templates/{slug}/versions/1.1.0/promote",
        headers=headers,
    )
    assert promote.status_code == 200, promote.text
    assert promote.json()["is_latest"] is True

    catalog = client.get(f"/api/v1/marketplace/templates/{slug}", headers=headers)
    assert catalog.status_code == 200
    assert catalog.json()["version"] == "1.1.0"

    history = client.get(f"/api/v1/marketplace/templates/{slug}/versions", headers=headers)
    assert history.status_code == 200
    versions = history.json()
    assert len(versions) >= 2
    latest = next(v for v in versions if v["is_latest"])
    assert latest["version"] == "1.1.0"

    one = client.get(f"/api/v1/marketplace/templates/{slug}/versions/1.0.0", headers=headers)
    assert one.status_code == 200
    assert one.json()["version"] == "1.0.0"
    assert one.json()["is_latest"] is False
