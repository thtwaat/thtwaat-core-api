"""Agent soft-delete, restore, retention, cleanup, and permission tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.agent_platform.lifecycle import AgentLifecycleService, RETENTION_DAYS, STATUS_DELETED
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase, KnowledgeBaseAgent
from app.rbac.enums import EnterpriseRole
from app.users.model import User


def _elevate(db_session, email: str, role: EnterpriseRole) -> None:
    row = db_session.query(User).filter(User.email == email).one()
    row.role = role
    db_session.commit()


def _auth(client, db_session, role: EnterpriseRole = EnterpriseRole.COMPANY_OWNER):
    company_slug = f"del-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Delete Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    # Public signup only allows company_owner / employee — elevate afterward.
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
        _elevate(db_session, email, role)

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id, user_id, email


def _create_agent(client, headers, name: str = "Delete Bot"):
    resp = client.post(
        "/v2/agents",
        json={
            "name": name,
            "description": "test",
            "system_prompt_template": "You are a helpful assistant.",
            "temperature": 0.2,
            "web_config": {"provider": "openai", "model": "gpt-4o-mini"},
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_soft_delete_hides_from_list(client, db_session):
    headers, _, _, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, headers)

    with patch("app.agent_platform.lifecycle.AgentLifecycleService._enqueue_cleanup"):
        resp = client.request(
            "DELETE",
            f"/v2/agents/{agent['id']}",
            headers=headers,
            json={"keep_conversations": True, "keep_knowledge": True},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == STATUS_DELETED
    assert data["retention_days"] == RETENTION_DAYS

    listed = client.get("/v2/agents", headers=headers)
    assert listed.status_code == 200
    assert all(a["id"] != agent["id"] for a in listed.json())

    missing = client.get(f"/v2/agents/{agent['id']}", headers=headers)
    assert missing.status_code == 404


def test_published_requires_confirm_unpublish(client, db_session):
    headers, _, _, _ = _auth(client, db_session, EnterpriseRole.ADMIN)
    agent = _create_agent(client, headers)
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200, pub.text

    blocked = client.request(
        "DELETE",
        f"/v2/agents/{agent['id']}",
        headers=headers,
        json={"confirm_unpublish": False},
    )
    assert blocked.status_code == 409, blocked.text

    with patch("app.agent_platform.lifecycle.AgentLifecycleService._enqueue_cleanup"):
        ok = client.request(
            "DELETE",
            f"/v2/agents/{agent['id']}",
            headers=headers,
            json={"confirm_unpublish": True},
        )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == STATUS_DELETED


def test_member_cannot_delete(client, db_session):
    owner_headers, company_id, _, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, owner_headers)

    email = f"emp-{uuid.uuid4().hex[:8]}@example.com"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Emp",
            "last_name": "User",
            "role": "employee",
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    emp_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.request(
        "DELETE",
        f"/v2/agents/{agent['id']}",
        headers=emp_headers,
        json={},
    )
    assert resp.status_code == 403, resp.text


def test_developer_cannot_delete(client, db_session):
    owner_headers, company_id, _, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, owner_headers)

    email = f"dev-{uuid.uuid4().hex[:8]}@example.com"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Dev",
            "last_name": "User",
            "role": "employee",
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    _elevate(db_session, email, EnterpriseRole.DEVELOPER)
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    dev_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.request(
        "DELETE",
        f"/v2/agents/{agent['id']}",
        headers=dev_headers,
        json={},
    )
    assert resp.status_code == 403, resp.text


def test_delete_impact_endpoint(client, db_session):
    headers, _, _, _ = _auth(client, db_session, EnterpriseRole.ADMIN)
    agent = _create_agent(client, headers)
    resp = client.get(f"/v2/agents/{agent['id']}/delete-impact", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["agent_id"] == agent["id"]
    assert "api_keys" in data
    assert data["retention_days"] == RETENTION_DAYS


def test_cleanup_detaches_knowledge_keeps_shared_kb(client, db_session):
    headers, company_id, user_id, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, headers)
    agent_id = uuid.UUID(agent["id"])
    company_uuid = uuid.UUID(company_id)

    kb = KnowledgeBase(company_id=company_uuid, name="Shared KB", description="keep me")
    db_session.add(kb)
    db_session.flush()
    db_session.add(KnowledgeBaseAgent(knowledge_base_id=kb.id, agent_id=agent_id))
    conv = Conversation(company_id=company_uuid, agent_id=agent_id, title="c1", channel="dashboard")
    db_session.add(conv)
    db_session.flush()
    db_session.add(Message(conversation_id=conv.id, role="user", content="hi"))
    db_session.commit()

    with patch("app.agent_platform.lifecycle.AgentLifecycleService._enqueue_cleanup"):
        svc = AgentLifecycleService(db_session)
        svc.soft_delete(
            agent_id=agent_id,
            company_id=company_uuid,
            user_id=uuid.UUID(user_id),
            keep_conversations=False,
            keep_knowledge=False,
            confirm_unpublish=False,
        )
        result = svc.run_cleanup(agent_id)

    assert result["ok"] is True
    assert result["deleted_conversations"] >= 1
    assert result["detached_knowledge"] >= 1
    assert db_session.query(KnowledgeBase).filter(KnowledgeBase.id == kb.id).first() is not None
    assert (
        db_session.query(KnowledgeBaseAgent)
        .filter(KnowledgeBaseAgent.agent_id == agent_id)
        .count()
        == 0
    )


def test_restore_within_retention_super_admin(client, db_session):
    headers, company_id, _, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, headers)

    with patch("app.agent_platform.lifecycle.AgentLifecycleService._enqueue_cleanup"):
        del_resp = client.request(
            "DELETE",
            f"/v2/agents/{agent['id']}",
            headers=headers,
            json={},
        )
    assert del_resp.status_code == 200, del_resp.text

    sa_headers, _, _, _ = _auth(client, db_session, EnterpriseRole.SUPER_ADMIN)

    restore = client.post(
        f"/v2/admin/agents/{agent['id']}/restore",
        headers=sa_headers,
        json={"reason": "accidental delete"},
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["status"] == "DRAFT"

    listed = client.get("/v2/agents", headers=headers)
    assert any(a["id"] == agent["id"] for a in listed.json())


def test_non_super_admin_cannot_restore(client, db_session):
    headers, _, _, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, headers)
    with patch("app.agent_platform.lifecycle.AgentLifecycleService._enqueue_cleanup"):
        client.request("DELETE", f"/v2/agents/{agent['id']}", headers=headers, json={})

    restore = client.post(
        f"/v2/admin/agents/{agent['id']}/restore",
        headers=headers,
        json={},
    )
    assert restore.status_code == 403, restore.text


def test_restore_after_retention_gone(client, db_session):
    headers, company_id, user_id, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, headers)
    agent_id = uuid.UUID(agent["id"])

    with patch("app.agent_platform.lifecycle.AgentLifecycleService._enqueue_cleanup"):
        AgentLifecycleService(db_session).soft_delete(
            agent_id=agent_id,
            company_id=uuid.UUID(company_id),
            user_id=uuid.UUID(user_id),
        )

    row = db_session.query(AgentConfig).filter(AgentConfig.id == agent_id).first()
    row.deleted_at = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS + 1)
    db_session.commit()

    sa_headers, _, _, _ = _auth(client, db_session, EnterpriseRole.SUPER_ADMIN)

    restore = client.post(
        f"/v2/admin/agents/{agent['id']}/restore",
        headers=sa_headers,
        json={},
    )
    assert restore.status_code == 410, restore.text


def test_purge_expired_hard_deletes(client, db_session):
    headers, company_id, user_id, _ = _auth(client, db_session, EnterpriseRole.ADMIN)
    agent = _create_agent(client, headers)
    agent_id = uuid.UUID(agent["id"])

    with patch("app.agent_platform.lifecycle.AgentLifecycleService._enqueue_cleanup"):
        AgentLifecycleService(db_session).soft_delete(
            agent_id=agent_id,
            company_id=uuid.UUID(company_id),
            user_id=uuid.UUID(user_id),
        )

    row = db_session.query(AgentConfig).filter(AgentConfig.id == agent_id).first()
    row.deleted_at = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS + 2)
    db_session.commit()

    with patch.object(AgentLifecycleService, "_clear_agent_caches", return_value=True):
        result = AgentLifecycleService(db_session).purge_expired()

    assert agent["id"] in result["purged"]
    assert db_session.query(AgentConfig).filter(AgentConfig.id == agent_id).first() is None


def test_worker_agent_cleanup_and_purge_jobs():
    from unittest.mock import MagicMock

    from scripts.worker import process_job

    mock_db = MagicMock()
    with patch("app.database.database.SessionLocal", return_value=mock_db):
        with patch("app.agent_platform.lifecycle.AgentLifecycleService.run_cleanup") as mock_cleanup:
            mock_cleanup.return_value = {"ok": True}
            process_job({"type": "agent.cleanup", "agent_id": str(uuid.uuid4())})
            assert mock_cleanup.called

        with patch("app.agent_platform.lifecycle.AgentLifecycleService.purge_expired") as mock_purge:
            mock_purge.return_value = {"purged": [], "count": 0}
            process_job({"type": "agent.purge_expired", "retention_days": 30})
            assert mock_purge.called

    mock_db.close.assert_called()


def test_unit_delete_impact_shape(client, db_session):
    headers, company_id, _, _ = _auth(client, db_session, EnterpriseRole.COMPANY_OWNER)
    agent = _create_agent(client, headers)
    row = db_session.query(AgentConfig).filter(AgentConfig.id == uuid.UUID(agent["id"])).one()
    row.web_config = {"suggested_prompts": ["a", "b"], "scheduled_jobs_count": 3}
    db_session.commit()

    impact = AgentLifecycleService(db_session).delete_impact(row)
    assert impact["draft_prompts"] == 2
    assert impact["scheduled_jobs"] == 3
    assert impact["widget"] is False
    assert impact["retention_days"] == RETENTION_DAYS
