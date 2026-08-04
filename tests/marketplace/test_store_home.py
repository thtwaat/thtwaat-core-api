"""Store Home v1 — home rails, collections, category meta, enrichment."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.marketplace.seed_store_home import seed_store_home
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"store-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Store Home Co", "slug": company_slug},
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


def _enable(db_session, company_id: str):
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)


def test_marketplace_home_rails(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    seed_marketplace_templates(db_session)
    seed_store_home(db_session)

    resp = client.get("/api/v1/marketplace/home", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in (
        "featured",
        "newest",
        "trending",
        "top_rated",
        "most_installed",
        "editors_choice",
        "continue_using",
        "recently_installed",
        "recently_viewed",
        "categories",
        "collections",
    ):
        assert key in body
    assert isinstance(body["categories"], list)
    assert any(c["slug"] == "saas" for c in body["categories"])
    # Additive category enrichment
    sample = next(c for c in body["categories"] if c["slug"] == "saas")
    assert "icon" in sample
    assert "popularity_score" in sample
    assert "is_featured" in sample
    assert isinstance(body["collections"], list)
    assert len(body["collections"]) >= 1


def test_collections_public_and_admin_crud(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    seed_marketplace_templates(db_session)

    listed = client.get("/api/v1/marketplace/templates", headers=headers)
    assert listed.status_code == 200
    template_id = listed.json()["items"][0]["id"]

    created = client.post(
        "/api/v1/marketplace/admin/collections",
        headers=headers,
        json={
            "slug": f"demo-{uuid.uuid4().hex[:6]}",
            "name": "Demo Collection",
            "description": "Test collection",
            "is_featured": True,
            "template_ids": [template_id],
        },
    )
    assert created.status_code == 201, created.text
    slug = created.json()["slug"]
    assert created.json()["item_count"] == 1
    assert created.json()["items"][0]["id"] == template_id

    public = client.get(f"/api/v1/marketplace/collections/{slug}", headers=headers)
    assert public.status_code == 200, public.text
    assert public.json()["slug"] == slug

    all_public = client.get("/api/v1/marketplace/collections", headers=headers)
    assert all_public.status_code == 200
    assert any(c["slug"] == slug for c in all_public.json())

    patched = client.patch(
        f"/api/v1/marketplace/admin/collections/{slug}",
        headers=headers,
        json={"name": "Demo Collection Renamed", "template_ids": []},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Demo Collection Renamed"
    assert patched.json()["item_count"] == 0

    deleted = client.delete(
        f"/api/v1/marketplace/admin/collections/{slug}",
        headers=headers,
    )
    assert deleted.status_code == 200


def test_template_response_enrichment_fields(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    seed_marketplace_templates(db_session)

    listed = client.get("/api/v1/marketplace/templates", headers=headers)
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    # Additive null-safe fields present
    for field in (
        "banner_url",
        "screenshots",
        "video_url",
        "live_demo_url",
        "verified_publisher",
        "publisher_slug",
        "company_name",
        "discount_percent",
        "rating_avg",
        "review_count",
        "download_count",
        "estimated_install_minutes",
        "compatibility",
        "is_editors_choice",
        "pricing_badge",
    ):
        assert field in item

    detail = client.get(f"/api/v1/marketplace/templates/{item['slug']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["pricing_badge"] in ("Free", "Pro", "Enterprise")

    # View event recorded → appears on home recently_viewed after second home fetch
    home = client.get("/api/v1/marketplace/home", headers=headers)
    assert home.status_code == 200
    viewed_slugs = {t["slug"] for t in home.json()["recently_viewed"]}
    assert item["slug"] in viewed_slugs


def test_install_still_works_with_store_home(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    seed_marketplace_templates(db_session)
    seed_store_home(db_session)

    install = client.post(
        "/api/v1/marketplace/templates/ai-saas-starter/install",
        headers=headers,
        json={"create_api_key": False},
    )
    assert install.status_code == 201, install.text

    home = client.get("/api/v1/marketplace/home", headers=headers)
    assert home.status_code == 200
    assert home.json()["installed_count"] >= 1
    recent = {t["slug"] for t in home.json()["recently_installed"]}
    assert "ai-saas-starter" in recent


def test_categories_include_new_verticals(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    seed_store_home(db_session)

    cats = client.get("/api/v1/marketplace/categories", headers=headers)
    assert cats.status_code == 200
    slugs = {c["slug"] for c in cats.json()}
    for expected in ("insurance", "devops", "productivity", "automation", "multilingual"):
        assert expected in slugs
