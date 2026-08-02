"""Phase 9: marketplace analytics endpoints."""
from __future__ import annotations

import uuid

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"mkt9-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Analytics Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]
    email = f"an-{uuid.uuid4().hex[:8]}@example.com"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Ana",
            "last_name": "Lytics",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    assert login_resp.status_code == 200, login_resp.text
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}, company_id


def test_marketplace_analytics_company_and_admin(client, db_session):
    headers, company_id = _auth(client, role="admin")
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    seed_marketplace_templates(db_session)

    install = client.post(
        "/api/v1/marketplace/templates/ai-website-starter/install",
        json={"create_api_key": False},
        headers=headers,
    )
    assert install.status_code in (200, 201), install.text

    company = client.get("/api/v1/marketplace/analytics?days=30", headers=headers)
    assert company.status_code == 200, company.text
    body = company.json()
    assert body["days"] == 30
    assert body["catalog"] is None
    assert body["company"]["installed_count"] >= 1
    assert len(body["company"]["installs_over_time"]) == 30
    assert any(p["installs"] >= 1 for p in body["company"]["installs_over_time"])

    admin = client.get("/api/v1/marketplace/admin/analytics?days=14", headers=headers)
    assert admin.status_code == 200, admin.text
    admin_body = admin.json()
    assert admin_body["days"] == 14
    assert admin_body["catalog"] is not None
    assert admin_body["catalog"]["templates_total"] >= 3
    assert admin_body["catalog"]["published"] >= 1
    assert len(admin_body["catalog"]["installs_over_time"]) == 14
    assert isinstance(admin_body["catalog"]["top_templates"], list)


def test_admin_analytics_forbidden_for_viewer(client, db_session):
    headers, company_id = _auth(client, role="viewer")
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)
    resp = client.get("/api/v1/marketplace/admin/analytics", headers=headers)
    assert resp.status_code == 403
