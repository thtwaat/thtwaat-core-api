"""Phase 3 template detail enrichment + reviews bridge."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"detail-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Detail Co", "slug": company_slug},
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


def test_template_detail_enrichment_fields(client, db_session):
    headers, company_id = _auth(client)
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    seed_marketplace_templates(db_session)

    listed = client.get("/api/v1/marketplace/templates", headers=headers)
    assert listed.status_code == 200
    slug = listed.json()["items"][0]["slug"]

    detail = client.get(f"/api/v1/marketplace/templates/{slug}", headers=headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    for field in (
        "feature_cards",
        "permissions",
        "languages",
        "license",
        "what_it_does",
        "best_for",
        "use_cases",
        "industries",
        "supported_providers",
        "dependencies",
        "listing_id",
    ):
        assert field in body
    assert isinstance(body["feature_cards"], list)
    assert len(body["feature_cards"]) >= 1
    assert isinstance(body["permissions"], list)


def test_template_reviews_endpoint(client, db_session):
    headers, company_id = _auth(client)
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    seed_marketplace_templates(db_session)

    listed = client.get("/api/v1/marketplace/templates", headers=headers)
    slug = listed.json()["items"][0]["slug"]
    reviews = client.get(f"/api/v1/marketplace/templates/{slug}/reviews", headers=headers)
    assert reviews.status_code == 200, reviews.text
    body = reviews.json()
    assert "items" in body
    assert "distribution" in body
    assert "review_count" in body
    assert body["template_id"]
