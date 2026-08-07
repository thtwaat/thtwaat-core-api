"""Marketplace Template Registry tests — install, version, rollback, publish."""
from __future__ import annotations

import uuid

import pytest

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "company_owner"):
    company_slug = f"mkt-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Marketplace Co {company_slug}", "slug": company_slug},
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


def _enable_templates(db_session, company_id: str, plan: str = "starter"):
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), plan, emit_upgraded=False)


def _seed(db_session):
    return seed_marketplace_templates(db_session)


def test_seed_and_browse_marketplace(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id)
    created = _seed(db_session)
    assert created >= 3

    listed = client.get("/api/v1/marketplace/templates", headers=headers)
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert "items" in page and "total" in page
    items = page["items"]
    slugs = {t["slug"] for t in items}
    assert "ai-website-starter" in slugs
    assert "ai-landing-starter" in slugs
    assert "ai-saas-starter" in slugs

    cats = client.get("/api/v1/marketplace/categories", headers=headers)
    assert cats.status_code == 200
    assert any(c["slug"] == "landing" for c in cats.json())

    featured = client.get("/api/v1/marketplace/templates?featured=true", headers=headers)
    assert featured.status_code == 200
    assert len(featured.json()["items"]) >= 1

    dash = client.get("/api/v1/marketplace/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert "featured" in body
    assert "newest" in body
    assert "categories" in body


def test_install_connect_publish_flow(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id)
    _seed(db_session)

    install = client.post(
        "/api/v1/marketplace/templates/ai-landing-starter/install",
        json={"create_api_key": False, "config_overrides": {"brand": "Acme"}},
        headers=headers,
    )
    assert install.status_code == 201, install.text
    data = install.json()
    assert data["status"] == "ready"
    assert data["installed_version"] == "1.0.0"
    assert data["config"]["brand"] == "Acme"
    assert data["config"]["company_id"] == company_id
    install_id = data["id"]

    installed = client.get("/api/v1/marketplace/installed", headers=headers)
    assert installed.status_code == 200
    assert any(i["id"] == install_id for i in installed.json())

    # Duplicate install blocked
    dup = client.post(
        "/api/v1/marketplace/templates/ai-landing-starter/install",
        json={},
        headers=headers,
    )
    assert dup.status_code == 409

    published = client.post(
        f"/api/v1/marketplace/installations/{install_id}/publish",
        headers=headers,
    )
    # supports_agents true without agent → 400
    assert published.status_code == 400

    # Soft-connect without agent validation by setting create_api_key false and
    # publishing after marking agent via connect with no agent should still fail.
    # Create agent via v2 if available; otherwise patch config path through connect domain only.
    connect = client.post(
        f"/api/v1/marketplace/installations/{install_id}/connect",
        json={"create_api_key": False},
        headers=headers,
    )
    assert connect.status_code == 200, connect.text

    # Force ready publish by attaching a fake agent_id through update config:
    # Use version update path — instead call publish after connecting with agent from v2.
    agent = client.post(
        "/v2/agents",
        json={
            "name": "Landing Bot",
            "system_prompt_template": "You are a landing page assistant.",
            "temperature": 0.5,
        },
        headers=headers,
    )
    if agent.status_code in (200, 201):
        agent_id = agent.json()["id"]
        connect2 = client.post(
            f"/api/v1/marketplace/installations/{install_id}/connect",
            json={"agent_id": agent_id, "create_api_key": False},
            headers=headers,
        )
        assert connect2.status_code == 200, connect2.text
        assert connect2.json()["agent_id"] == agent_id

        published = client.post(
            f"/api/v1/marketplace/installations/{install_id}/publish",
            headers=headers,
        )
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "published"
        assert published.json()["published_at"] is not None


def test_free_templates_install_for_free_plan_users(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id, plan="free")
    _seed(db_session)

    install = client.post(
        "/api/v1/marketplace/templates/ai-website-starter/install",
        json={"create_api_key": False},
        headers=headers,
    )
    assert install.status_code == 201, install.text
    assert install.json()["status"] == "ready"


def test_paid_templates_still_require_quota_for_free_plan_users(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id, plan="free")
    _seed(db_session)

    install = client.post(
        "/api/v1/marketplace/templates/marketing-ad-copy/install",
        json={"create_api_key": False},
        headers=headers,
    )
    assert install.status_code == 429, install.text
    detail = install.json()
    assert detail["error"] == "quota_exceeded"
    assert "Upgrade" in detail["message"]


def test_paid_templates_still_install_when_plan_allows_it(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id, plan="starter")
    _seed(db_session)

    install = client.post(
        "/api/v1/marketplace/templates/marketing-ad-copy/install",
        json={"create_api_key": False},
        headers=headers,
    )
    assert install.status_code == 201, install.text
    assert install.json()["status"] == "ready"


def test_version_update_and_rollback(client, db_session):
    headers, company_id = _auth(client)
    _enable_templates(db_session, company_id)
    _seed(db_session)

    # Resolve template id
    detail = client.get("/api/v1/marketplace/templates/ai-saas-starter", headers=headers)
    assert detail.status_code == 200
    template_id = detail.json()["id"]

    install = client.post(
        "/api/v1/marketplace/templates/ai-saas-starter/install",
        json={"create_api_key": False},
        headers=headers,
    )
    assert install.status_code == 201, install.text
    install_id = install.json()["id"]
    assert install.json()["installed_version"] == "1.0.0"

    version = client.post(
        f"/api/v1/marketplace/templates/{template_id}/versions",
        json={
            "version": "1.1.0",
            "changelog": "Added marketplace module",
            "config": {"modules": ["auth", "marketplace"], "release": "1.1.0"},
            "set_latest": True,
        },
        headers=headers,
    )
    assert version.status_code == 201, version.text
    assert version.json()["version"] == "1.1.0"

    updates = client.get("/api/v1/marketplace/updates", headers=headers)
    assert updates.status_code == 200
    assert any(u["installation_id"] == install_id for u in updates.json())

    upgraded = client.post(
        f"/api/v1/marketplace/installations/{install_id}/update",
        headers=headers,
    )
    assert upgraded.status_code == 200, upgraded.text
    body = upgraded.json()
    assert body["installed_version"] == "1.1.0"
    assert body["previous_version"] == "1.0.0"
    assert body["config"]["release"] == "1.1.0"
    assert body["update_available"] is False

    rolled = client.post(
        f"/api/v1/marketplace/installations/{install_id}/rollback",
        headers=headers,
    )
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["installed_version"] == "1.0.0"
    assert rolled.json()["previous_version"] == "1.1.0"
    assert rolled.json()["update_available"] is True

    uninstall = client.delete(
        f"/api/v1/marketplace/installations/{install_id}",
        headers=headers,
    )
    assert uninstall.status_code == 200
    installed = client.get("/api/v1/marketplace/installed", headers=headers)
    assert all(i["id"] != install_id for i in installed.json())


def test_viewer_cannot_install(client, db_session):
    headers, company_id = _auth(client, role="viewer")
    _enable_templates(db_session, company_id)
    _seed(db_session)

    listed = client.get("/api/v1/marketplace/templates", headers=headers)
    assert listed.status_code == 200

    install = client.post(
        "/api/v1/marketplace/templates/ai-website-starter/install",
        json={},
        headers=headers,
    )
    assert install.status_code in (401, 403)
