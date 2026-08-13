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


def _bearer_for_user(db_session, user_id: str) -> dict:
    """Mint a JWT without /auth/login so suites are not blocked by login rate limits."""
    from app.auth.service import AuthService

    token = AuthService(db_session).create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


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

    return _bearer_for_user(db_session, user_id), company_id, user_id


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


def test_create_agent_is_always_blank_and_never_touches_an_existing_agent(client, db_session):
    """New Agent must create a fresh, independent agent — never inherit fields from,
    reference, or mutate another agent, regardless of what else exists in the company."""
    headers, company_id, _ = _auth(client, db_session)
    _raise_agent_quota(db_session, company_id)

    source = _create_agent(
        client,
        headers,
        name="Viral Awaaz Assistant",
        description="Original source agent",
        system_prompt_template="You are the Viral Awaaz assistant.",
        temperature=0.4,
    )

    fresh = _create_agent(
        client,
        headers,
        name="THTWAAT Support Agent",
        description="Support bot",
        system_prompt_template="You are a helpful support agent.",
        temperature=0.2,
    )

    # The new agent must be exactly what was requested — no "Copy of" prefix,
    # no inherited fields, and a distinct id/slug from the source agent.
    assert fresh["id"] != source["id"]
    assert fresh["name"] == "THTWAAT Support Agent"
    assert not fresh["name"].startswith("Copy of")
    assert fresh["slug"] != source["slug"]
    assert fresh["system_prompt_template"] == "You are a helpful support agent."
    assert fresh["temperature"] == 0.2

    # The source agent must be completely unaffected by creating the new one.
    refetched_source = client.get(f"/v2/agents/{source['id']}", headers=headers)
    assert refetched_source.status_code == 200
    unchanged = refetched_source.json()
    assert unchanged["name"] == "Viral Awaaz Assistant"
    assert unchanged["system_prompt_template"] == "You are the Viral Awaaz assistant."
    assert unchanged["temperature"] == 0.4

    # Both agents show up as separate entries.
    listing = client.get("/v2/agents", headers=headers)
    assert listing.status_code == 200
    names = {a["name"] for a in listing.json()}
    assert {"Viral Awaaz Assistant", "THTWAAT Support Agent"} <= names


def test_clone_agent_produces_a_copy_and_leaves_source_unchanged(client, db_session):
    """Duplicate is the only flow responsible for cloning — it must prefix the
    copy's name, create a distinct DRAFT agent, and never mutate the source."""
    headers, company_id, _ = _auth(client, db_session)
    _raise_agent_quota(db_session, company_id)

    source = _create_agent(
        client,
        headers,
        name="Viral Awaaz Assistant",
        system_prompt_template="You are the Viral Awaaz assistant.",
        temperature=0.4,
    )

    clone_resp = client.post(f"/v2/agents/{source['id']}/clone", headers=headers)
    assert clone_resp.status_code == 200, clone_resp.text
    cloned = clone_resp.json()

    assert cloned["id"] != source["id"]
    assert cloned["name"] == "Copy of Viral Awaaz Assistant"
    assert cloned["status"] == "DRAFT"
    assert cloned["system_prompt_template"] == source["system_prompt_template"]

    # Cloning must not rename, migrate, or otherwise mutate the source agent.
    refetched_source = client.get(f"/v2/agents/{source['id']}", headers=headers)
    assert refetched_source.status_code == 200
    unchanged = refetched_source.json()
    assert unchanged["name"] == "Viral Awaaz Assistant"
    assert unchanged["id"] == source["id"]
    assert unchanged["system_prompt_template"] == "You are the Viral Awaaz assistant."

    # Both agents show up as separate entries.
    listing = client.get("/v2/agents", headers=headers)
    assert listing.status_code == 200
    names = {a["name"] for a in listing.json()}
    assert {"Viral Awaaz Assistant", "Copy of Viral Awaaz Assistant"} <= names


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
        from app.users.model import User

        row = db_session.query(User).filter(User.email == email).one()
        if role != EnterpriseRole.EMPLOYEE:
            row.role = role
            db_session.commit()

        member_headers = _bearer_for_user(db_session, str(row.id))

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


def _member_headers(client, db_session, company_id: str, role: EnterpriseRole):
    """Create a same-company member with the given enterprise role and return auth headers."""
    from app.users.model import User

    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Member",
            "last_name": "User",
            "role": "employee",
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    row = db_session.query(User).filter(User.email == email).one()
    if role != EnterpriseRole.EMPLOYEE:
        row.role = role
        db_session.commit()
    return _bearer_for_user(db_session, str(row.id))


def test_agent_rbac_unauthorized_role_rejected(client, db_session):
    """Viewer/employee lack create/publish/manage_keys — mutating routes must 403."""
    owner_headers, company_id, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, owner_headers)
    viewer = _member_headers(client, db_session, company_id, EnterpriseRole.VIEWER)

    create_resp = client.post(
        "/v2/agents",
        json={
            "name": "Forbidden Bot",
            "system_prompt_template": "Nope",
            "web_config": {},
        },
        headers=viewer,
    )
    assert create_resp.status_code == 403, create_resp.text

    publish_resp = client.post(f"/v2/agents/{agent['id']}/publish", headers=viewer)
    assert publish_resp.status_code == 403, publish_resp.text

    keys_resp = client.post(f"/v2/agents/{agent['id']}/api-keys", headers=viewer)
    assert keys_resp.status_code == 403, keys_resp.text

    clone_resp = client.post(f"/v2/agents/{agent['id']}/clone", headers=viewer)
    assert clone_resp.status_code == 403, clone_resp.text


def test_agent_rbac_authorized_role_allowed(client, db_session):
    """Company owner may create/list; admin may publish; developer may manage keys."""
    owner_headers, company_id, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    _raise_agent_quota(db_session, company_id)

    create_resp = client.post(
        "/v2/agents",
        json={
            "name": "RBAC Allowed",
            "system_prompt_template": "You are helpful.",
            "web_config": {},
        },
        headers=owner_headers,
    )
    assert create_resp.status_code in (200, 201), create_resp.text
    agent_id = create_resp.json()["id"]

    list_resp = client.get("/v2/agents", headers=owner_headers)
    assert list_resp.status_code == 200, list_resp.text
    assert any(a["id"] == agent_id for a in list_resp.json())

    admin = _member_headers(client, db_session, company_id, EnterpriseRole.ADMIN)
    publish_resp = client.post(f"/v2/agents/{agent_id}/publish", headers=admin)
    assert publish_resp.status_code == 200, publish_resp.text

    developer = _member_headers(client, db_session, company_id, EnterpriseRole.DEVELOPER)
    keys_resp = client.post(f"/v2/agents/{agent_id}/api-keys", headers=developer)
    assert keys_resp.status_code in (200, 201), keys_resp.text


def test_agent_rbac_cross_company_access_rejected(client, db_session):
    headers_a, _, _ = _auth(client, db_session)
    headers_b, _, _ = _auth(client, db_session)
    agent = _create_agent(client, headers_a)

    assert client.get(f"/v2/agents/{agent['id']}", headers=headers_b).status_code == 404
    assert client.post(f"/v2/agents/{agent['id']}/publish", headers=headers_b).status_code == 404
    assert client.post(f"/v2/agents/{agent['id']}/api-keys", headers=headers_b).status_code == 404
    assert client.post(f"/v2/agents/{agent['id']}/clone", headers=headers_b).status_code == 404


def test_viral_awaaz_cannot_be_created_as_template(client, db_session):
    headers, _, _ = _auth(client, db_session)
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Viral Awaaz Assistant",
            "system_prompt_template": "You are the Viral Awaaz assistant.",
            "is_template": True,
            "web_config": {},
        },
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    message = str(body.get("detail") or body.get("error") or body).lower()
    assert "template" in message


def test_viral_awaaz_excluded_from_templates_and_cross_company_clone(client, db_session):
    """Even if marked is_template in DB, Viral Awaaz must not leak via templates/clone."""
    from app.agent_platform.models.agent import AgentConfig

    headers_a, company_a, _ = _auth(client, db_session)
    headers_b, company_b, _ = _auth(client, db_session)
    _raise_agent_quota(db_session, company_a)
    _raise_agent_quota(db_session, company_b)

    source = _create_agent(
        client,
        headers_a,
        name="Viral Awaaz Assistant",
        system_prompt_template="You are the Viral Awaaz assistant.",
    )
    # Simulate accidental template flag in DB without changing prompt/config via API.
    row = db_session.query(AgentConfig).filter(AgentConfig.id == UUID(source["id"])).one()
    original_prompt = row.system_prompt_template
    original_name = row.name
    row.is_template = True
    db_session.commit()

    templates = client.get("/v2/agents/templates", headers=headers_b)
    assert templates.status_code == 200, templates.text
    assert all(t["id"] != source["id"] for t in templates.json())
    assert all(t.get("name") != "Viral Awaaz Assistant" for t in templates.json())

    clone_cross = client.post(f"/v2/agents/{source['id']}/clone", headers=headers_b)
    assert clone_cross.status_code == 404, clone_cross.text

    # Same-company clone still allowed; source prompt/name untouched.
    clone_same = client.post(f"/v2/agents/{source['id']}/clone", headers=headers_a)
    assert clone_same.status_code == 200, clone_same.text
    assert clone_same.json()["name"] == "Copy of Viral Awaaz Assistant"

    refreshed = db_session.query(AgentConfig).filter(AgentConfig.id == UUID(source["id"])).one()
    assert refreshed.name == original_name
    assert refreshed.system_prompt_template == original_prompt
