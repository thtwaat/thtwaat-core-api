"""Phase 7: marketplace FTS search behavior (Postgres integration)."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"mkt7-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "FTS Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]
    email = f"fts-{uuid.uuid4().hex[:8]}@example.com"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Fts",
            "last_name": "User",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    assert login_resp.status_code == 200, login_resp.text
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}, company_id


def test_fts_search_matches_name_description_and_tags(client, db_session):
    headers, company_id = _auth(client)
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    seed_marketplace_templates(db_session)

    created = client.post(
        "/api/v1/marketplace/templates",
        json={
            "slug": f"fts-{uuid.uuid4().hex[:6]}",
            "name": "Zephyr Outline Composer",
            "category": "writing",
            "kind": "prompt",
            "description": "Helps draft long-form articles about nebula research",
            "tags": ["nebula", "outline", "writing"],
            "publish": True,
            "default_config": {"prompt": "Write about {{topic}}"},
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]

    by_name = client.get("/api/v1/marketplace/templates?q=Zephyr", headers=headers)
    assert by_name.status_code == 200, by_name.text
    assert any(i["id"] == tid for i in by_name.json()["items"])
    assert by_name.json()["sort"] == "relevance"

    by_desc = client.get("/api/v1/marketplace/templates?q=nebula", headers=headers)
    assert by_desc.status_code == 200
    assert any(i["id"] == tid for i in by_desc.json()["items"])

    by_tag = client.get("/api/v1/marketplace/templates?q=outline", headers=headers)
    assert by_tag.status_code == 200
    assert any(i["id"] == tid for i in by_tag.json()["items"])

    miss = client.get("/api/v1/marketplace/templates?q=zzzz-no-such-token", headers=headers)
    assert miss.status_code == 200
    assert all(i["id"] != tid for i in miss.json()["items"])
