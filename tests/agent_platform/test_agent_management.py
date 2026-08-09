"""Tests for agent create/update, company isolation, RBAC, publish validation, and clone."""
from __future__ import annotations

import uuid
from uuid import UUID

from app.rbac.enums import EnterpriseRole


def _raise_agent_quota(db_session, company_id: str) -> None:
    """Free plan caps agents_count at 1 — bump to starter (5) for tests needing >1 agent/company."""
    from app.companies.model import Company, CompanyPlan

    company = db_session.query(Company).filter(Company.id == UUID(company_id)).one()
    company.plan = CompanyPlan.STARTER
    db_session.commit()


def _auth(client, db_session, role: EnterpriseRole = EnterpriseRole.COMPANY_OWNER):
    from app.users.model import User

    company_slug = f"mgmt-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Mgmt Co {company_slug}", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    signup_role = (
        "company_owner"
        if role in (EnterpriseRole.COMPANY_OWNER, EnterpriseRole.SUPER_ADMIN, EnterpriseRole.ADMIN)
        else "employee"
    )
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Test",
            "last_name": "User",
            "role": signup_role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    user_id = user_resp.json()["id"]

    if role.value != signup_role:
        row = db_session.query(User).filter(User.email == email).one()
        row.role = role
        db_session.commit()

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id, user_id


def _create_agent(client, headers, **overrides):
    body = {
        "name": "Mgmt Bot",
        "description": "test",
        "system_prompt_template": "You are a helpful assistant.",
        "temperature": 0.2,
        "web_config": {},
    }
    body.update(overrides)
    resp = client.post("/v2/agents", json=body, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_create_agent_autogenerates_slug(client, db_session):
    headers, _, _ = _auth(client, db_session)
    agent = _create_agent(client, headers, name="Sales Assistant")
    assert agent["slug"] == "sales-assistant"
    assert agent["provider"] is None
    assert agent["allowed_tools"] == []


def test_create_agent_unique_slug_per_company(client, db_session):
    headers, company_id, _ = _auth(client, db_session)
    _raise_agent_quota(db_session, company_id)
    a1 = _create_agent(client, headers, name="Dup Name")
    a2 = _create_agent(client, headers, name="Dup Name")
    assert a1["slug"] == "dup-name"
    assert a2["slug"] == "dup-name-2"


def test_company_isolation_get_and_patch(client, db_session):
    headers_a, _, _ = _auth(client, db_session)
    headers_b, _, _ = _auth(client, db_session)
    agent = _create_agent(client, headers_a)

    get_cross = client.get(f"/v2/agents/{agent['id']}", headers=headers_b)
    assert get_cross.status_code == 404

    patch_cross = client.patch(
        f"/v2/agents/{agent['id']}",
        json={"name": "Hijacked"},
        headers=headers_b,
    )
    assert patch_cross.status_code == 404


def test_company_isolation_clone(client, db_session):
    """Cloning another company's (non-template) agent must not be possible."""
    headers_a, _, _ = _auth(client, db_session)
    headers_b, _, _ = _auth(client, db_session)
    agent = _create_agent(client, headers_a)

    resp = client.post(f"/v2/agents/{agent['id']}/clone", headers=headers_b)
    assert resp.status_code == 404


def test_update_agent_rbac_forbidden_for_viewer_and_employee(client, db_session):
    owner_headers, company_id, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, owner_headers)

    for role in (EnterpriseRole.VIEWER, EnterpriseRole.EMPLOYEE):
        email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
        user_resp = client.post(
            "/api/v1/users/",
            json={
                "email": email,
                "password": "securepassword",
                "company_id": company_id,
                "first_name": "Restricted",
                "last_name": "User",
                "role": "employee",
            },
        )
        assert user_resp.status_code in (200, 201), user_resp.text
        if role != EnterpriseRole.EMPLOYEE:
            from app.users.model import User

            row = db_session.query(User).filter(User.email == email).one()
            row.role = role
            db_session.commit()

        login = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
        member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = client.patch(
            f"/v2/agents/{agent['id']}",
            json={"name": "Nope"},
            headers=member_headers,
        )
        assert resp.status_code == 403, f"{role} should not be able to update agents"


def test_update_agent_applies_changes(client, db_session):
    headers, _, _ = _auth(client, db_session, EnterpriseRole.ADMIN)
    agent = _create_agent(client, headers)

    resp = client.patch(
        f"/v2/agents/{agent['id']}",
        json={
            "system_prompt_template": "You are a pirate.",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "temperature": 0.9,
            "allowed_tools": ["knowledge_search"],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["system_prompt_template"] == "You are a pirate."
    assert data["provider"] == "anthropic"
    assert data["model"] == "claude-3-5-sonnet"
    assert data["temperature"] == 0.9
    assert data["allowed_tools"] == ["knowledge_search"]

    # Slug is immutable via PATCH (never included in AgentUpdate).
    fetched = client.get(f"/v2/agents/{agent['id']}", headers=headers)
    assert fetched.json()["slug"] == agent["slug"]


def test_publish_rejects_agent_with_empty_instructions(client, db_session):
    headers, _, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, headers)

    # Blank out instructions via PATCH, then attempt to publish.
    client.patch(
        f"/v2/agents/{agent['id']}",
        json={"system_prompt_template": "   "},
        headers=headers,
    )
    resp = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"] == "agent_not_ready"


def test_list_available_tools_includes_knowledge_search(client, db_session):
    headers, _, _ = _auth(client, db_session)
    resp = client.get("/v2/agents/tools", headers=headers)
    assert resp.status_code == 200, resp.text
    names = [t["name"] for t in resp.json()]
    assert "knowledge_search" in names
