"""Cross-company knowledge-base attach isolation."""
from __future__ import annotations

import uuid
from uuid import UUID

from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase, KnowledgeBaseAgent
from app.rbac.enums import EnterpriseRole


def _auth(client, db_session, role: EnterpriseRole = EnterpriseRole.COMPANY_OWNER):
    from app.auth.service import AuthService
    from app.users.model import User

    company_slug = f"kbiso-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"KB Iso {company_slug}", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Test",
            "last_name": "User",
            "role": "company_owner",
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    user_id = user_resp.json()["id"]

    if role.value != "company_owner":
        row = db_session.query(User).filter(User.email == email).one()
        row.role = role
        db_session.commit()

    token = AuthService(db_session).create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}, company_id


def _create_agent(client, headers):
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Attach Bot",
            "description": "test",
            "system_prompt_template": "You are helpful.",
            "temperature": 0.2,
            "web_config": {},
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_attach_rejects_company_a_agent_with_company_b_kb(client, db_session):
    """Company A agent + Company B KB must be rejected (no cross-tenant attach)."""
    headers_a, company_a = _auth(client, db_session)
    headers_b, company_b = _auth(client, db_session)

    agent_a = _create_agent(client, headers_a)

    kb_b = KnowledgeBase(company_id=UUID(company_b), name="Company B KB")
    db_session.add(kb_b)
    db_session.commit()
    db_session.refresh(kb_b)

    resp = client.post(
        f"/v2/knowledge/bases/{kb_b.id}/agents/{agent_a['id']}",
        headers=headers_a,
    )
    assert resp.status_code == 404, resp.text

    # No attachment row should exist.
    link = (
        db_session.query(KnowledgeBaseAgent)
        .filter(
            KnowledgeBaseAgent.knowledge_base_id == kb_b.id,
            KnowledgeBaseAgent.agent_id == UUID(agent_a["id"]),
        )
        .first()
    )
    assert link is None


def test_attach_rejects_company_a_kb_with_company_b_agent(client, db_session):
    """Same-company KB cannot be attached to another company's agent."""
    headers_a, company_a = _auth(client, db_session)
    headers_b, _company_b = _auth(client, db_session)

    agent_b = _create_agent(client, headers_b)
    kb_a = KnowledgeBase(company_id=UUID(company_a), name="Company A KB")
    db_session.add(kb_a)
    db_session.commit()
    db_session.refresh(kb_a)

    resp = client.post(
        f"/v2/knowledge/bases/{kb_a.id}/agents/{agent_b['id']}",
        headers=headers_a,
    )
    assert resp.status_code == 404, resp.text

    link = (
        db_session.query(KnowledgeBaseAgent)
        .filter(
            KnowledgeBaseAgent.knowledge_base_id == kb_a.id,
            KnowledgeBaseAgent.agent_id == UUID(agent_b["id"]),
        )
        .first()
    )
    assert link is None


def test_attach_same_company_still_works(client, db_session):
    headers, company_id = _auth(client, db_session)
    agent = _create_agent(client, headers)

    kb = KnowledgeBase(company_id=UUID(company_id), name="Same Co KB")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    resp = client.post(
        f"/v2/knowledge/bases/{kb.id}/agents/{agent['id']}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    link = (
        db_session.query(KnowledgeBaseAgent)
        .filter(
            KnowledgeBaseAgent.knowledge_base_id == kb.id,
            KnowledgeBaseAgent.agent_id == UUID(agent["id"]),
        )
        .first()
    )
    assert link is not None
    # Agent row unchanged aside from attachment.
    row = db_session.query(AgentConfig).filter(AgentConfig.id == UUID(agent["id"])).one()
    assert row.name == "Attach Bot"
