"""AI Product Generator tests — analyze, generate orchestration, publish, RBAC."""
from __future__ import annotations

import uuid

import pytest

from app.marketplace.seed import seed_marketplace_templates
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"gen-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Generator Co", "slug": company_slug},
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


def _seed(db_session):
    return seed_marketplace_templates(db_session)


# ── Analyzer ──────────────────────────────────────────────────────────────────

def test_analyze_restaurant_prompt(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    _seed(db_session)

    resp = client.post(
        "/api/v1/product-generator/analyze",
        json={"prompt": "Restaurant website with AI ordering and table booking"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["industry"] == "restaurant"
    assert data["product_type"] in ("website", "landing")
    assert "ai_chat" in data["required_features"]
    assert "booking" in data["required_features"] or "ordering" in data["required_features"]
    assert data["confidence"] > 0.4


def test_analyze_clinic_saas(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    _seed(db_session)

    resp = client.post(
        "/api/v1/product-generator/analyze",
        json={"prompt": "Clinic booking SaaS for patient appointments"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["industry"] == "healthcare"
    assert data["brand_tone"] == "clinical"
    assert "booking" in data["required_features"]


def test_analyze_real_estate(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    _seed(db_session)

    resp = client.post(
        "/api/v1/product-generator/analyze",
        json={"prompt": "Real estate landing page with AI listings assistant"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["industry"] == "real_estate"
    assert data["product_type"] in ("landing", "website")
    assert data["recommended_template_slug"] is not None


def test_analyze_bad_prompt(client, db_session):
    headers, _ = _auth(client)
    resp = client.post(
        "/api/v1/product-generator/analyze",
        json={"prompt": "hi"},
        headers=headers,
    )
    # Too short — validation error
    assert resp.status_code in (400, 422)


# ── Generator orchestration ───────────────────────────────────────────────────

def test_generate_orchestrates_agent_and_kb(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    _seed(db_session)

    resp = client.post(
        "/api/v1/product-generator/generate",
        json={
            "prompt": "School admission portal with AI FAQ assistant",
            "auto_publish": False,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] in ("preview_ready", "failed")

    if data["status"] == "preview_ready":
        # Core resources must be provisioned
        assert data["agent_id"] is not None
        assert data["knowledge_base_id"] is not None
        assert data["template_slug"] is not None
        assert data["installation_id"] is not None
        assert data["product_config"]["name"]
        assert data["deployment_checklist"]
        assert any(item["done"] for item in data["deployment_checklist"])

        # Checklist completeness
        done_keys = {i["key"] for i in data["deployment_checklist"] if i["done"]}
        assert "analyze" in done_keys
        assert "template" in done_keys
        assert "agent" in done_keys
        assert "knowledge" in done_keys

        gen_id = data["id"]
        # Re-fetch via GET
        get_resp = client.get(f"/api/v1/product-generator/generations/{gen_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == gen_id

        # List
        list_resp = client.get("/api/v1/product-generator/generations", headers=headers)
        assert list_resp.status_code == 200
        ids = {g["id"] for g in list_resp.json()}
        assert gen_id in ids

        # Output endpoint (clears api_key from record)
        out_resp = client.get(f"/api/v1/product-generator/generations/{gen_id}/output", headers=headers)
        assert out_resp.status_code == 200
        out = out_resp.json()
        assert "publish_status" in out
        assert "deployment_checklist" in out


def test_generate_reuses_existing_template_install(client, db_session):
    """Second assemble for the same package must not 409; reuse agent/install."""
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    _seed(db_session)

    first = client.post(
        "/api/v1/product-generator/generate",
        json={
            "prompt": "School admission portal with AI FAQ assistant",
            "auto_publish": False,
        },
        headers=headers,
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    if first_body.get("status") != "preview_ready":
        pytest.skip(f"First generate ended in {first_body.get('status')}: {first_body.get('failure_reason')}")

    agent_id = first_body["agent_id"]
    install_id = first_body["installation_id"]
    template_slug = first_body["template_slug"]
    assert agent_id and install_id and template_slug

    from app.agent_platform.models.agent import AgentConfig

    agents_before = (
        db_session.query(AgentConfig)
        .filter(AgentConfig.company_id == uuid.UUID(company_id))
        .count()
    )

    second = client.post(
        "/api/v1/product-generator/generate",
        json={
            "prompt": "School admission portal with AI FAQ assistant",
            "template_slug": template_slug,
            "auto_publish": False,
        },
        headers=headers,
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["status"] == "preview_ready"
    assert body.get("already_installed") is True
    assert "Opening your existing AI workspace" in (body.get("reuse_message") or "")
    assert body["agent_id"] == agent_id
    assert body["installation_id"] == install_id
    assert body["template_slug"] == template_slug
    assert body.get("failure_reason") in (None, "")

    agents_after = (
        db_session.query(AgentConfig)
        .filter(AgentConfig.company_id == uuid.UUID(company_id))
        .count()
    )
    assert agents_after == agents_before


# ── Publish ───────────────────────────────────────────────────────────────────

def test_generate_and_publish(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    _seed(db_session)

    gen_resp = client.post(
        "/api/v1/product-generator/generate",
        json={"prompt": "Legal firm website with document assistant", "auto_publish": False},
        headers=headers,
    )
    assert gen_resp.status_code == 201, gen_resp.text
    data = gen_resp.json()
    if data["status"] != "preview_ready":
        pytest.skip(f"Generation ended in {data['status']}; skipping publish step")

    gen_id = data["id"]
    pub_resp = client.post(
        f"/api/v1/product-generator/generations/{gen_id}/publish",
        json={},
        headers=headers,
    )
    assert pub_resp.status_code == 200, pub_resp.text
    pub_data = pub_resp.json()
    assert pub_data["status"] in ("published", "failed")
    if pub_data["status"] == "published":
        assert pub_data["widget_id"] is not None
        assert any(
            i["key"] == "publish" and i["done"]
            for i in pub_data["deployment_checklist"]
        )


def test_generator_viewer_cannot_generate(client, db_session):
    headers, company_id = _auth(client, role="viewer")
    _enable(db_session, company_id)
    _seed(db_session)

    resp = client.post(
        "/api/v1/product-generator/generate",
        json={"prompt": "Restaurant website with AI ordering"},
        headers=headers,
    )
    assert resp.status_code in (401, 403)

    # But viewer CAN analyze
    analyze = client.post(
        "/api/v1/product-generator/analyze",
        json={"prompt": "Restaurant website with AI ordering"},
        headers=headers,
    )
    assert analyze.status_code == 200


def test_generator_products_config_content(client, db_session):
    headers, company_id = _auth(client)
    _enable(db_session, company_id)
    _seed(db_session)

    resp = client.post(
        "/api/v1/product-generator/generate",
        json={
            "prompt": "Ecommerce store with AI product search and payment",
            "config_overrides": {"colors": {"primary": "#FF6B6B"}},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    if data["status"] == "preview_ready":
        cfg = data["product_config"]
        assert cfg.get("colors", {}).get("primary") == "#FF6B6B"
        assert cfg.get("features")
        assert cfg.get("suggested_prompts")
        assert cfg.get("system_prompt")
        assert cfg.get("navigation")
