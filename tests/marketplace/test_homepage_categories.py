"""Regression: homepage categories + catalog rails from seeded templates."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.marketplace.seed_store_home import seed_store_home
from app.usage.service import UsageService


def _auth(client):
    company_slug = f"cats-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Categories Co", "slug": company_slug},
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
            "role": "admin",
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}, company_id


def test_categories_api_reflects_seeded_catalog(client, db_session):
    headers, company_id = _auth(client)
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    assert seed_marketplace_templates(db_session) >= 1
    seed_store_home(db_session)

    cats = client.get("/api/v1/marketplace/categories", headers=headers)
    assert cats.status_code == 200, cats.text
    body = cats.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    populated = [c for c in body if (c.get("count") or c.get("template_count") or 0) > 0]
    assert populated, "expected at least one category with seeded templates"
    assert all("slug" in c and "name" in c for c in body)


def test_home_returns_categories_and_rails_after_seed(client, db_session):
    headers, company_id = _auth(client)
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    seed_marketplace_templates(db_session)
    seed_store_home(db_session)

    home = client.get("/api/v1/marketplace/home", headers=headers)
    assert home.status_code == 200, home.text
    body = home.json()
    assert body["categories"], "home.categories must not be empty after seed"
    populated = [c for c in body["categories"] if (c.get("count") or 0) > 0]
    assert populated
    # At least one discovery rail should surface seeded templates
    rail_total = sum(
        len(body.get(key) or [])
        for key in ("featured", "newest", "trending", "most_installed", "editors_choice")
    )
    assert rail_total >= 1, "expected featured/trending/new rails to include catalog templates"

    listed = client.get("/api/v1/marketplace/templates?limit=5", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
