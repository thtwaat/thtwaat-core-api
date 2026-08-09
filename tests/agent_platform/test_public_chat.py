"""Tests for the public chat surface: auth failures, quota, pause, and slug routing."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from uuid import UUID


def _auth(client, role: str = "company_owner"):
    company_slug = f"pubchat-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Public Chat Co {company_slug}", "slug": company_slug},
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


def _create_and_publish_agent(client, headers, name: str = "Public Bot"):
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
    agent = resp.json()

    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return agent, pub.json()


_FAKE_AI_RESULT = type(
    "R",
    (),
    {
        "content": "Hello from AI",
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
        "estimated_cost": 0.0,
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tool_calls": None,
    },
)()


def test_invalid_api_key_returns_401(client):
    resp = client.post(
        "/public/v1/chat",
        json={"api_key": "tht_live_totally-bogus-key", "message": "hi"},
    )
    assert resp.status_code == 401


def test_missing_bearer_returns_401(client):
    resp = client.post("/public/v1/chat", json={"message": "hi"})
    assert resp.status_code == 401


def test_paused_agent_blocks_chat(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers)
    api_key = pub["api_key"]

    paused = client.post(f"/api/v1/agents/{agent['id']}/pause", headers=headers)
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "PAUSED"

    chat = client.post(
        "/public/v1/chat",
        json={"api_key": api_key, "message": "hello"},
    )
    assert chat.status_code == 400
    assert "paused" in chat.text.lower()


def test_resume_restores_chat(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers)
    api_key = pub["api_key"]

    client.post(f"/api/v1/agents/{agent['id']}/pause", headers=headers)
    resumed = client.post(f"/api/v1/agents/{agent['id']}/resume", headers=headers)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "PUBLISHED"

    with patch(
        "app.agent_platform.routers.public_router.AIGatewayService.process_request",
        new=AsyncMock(return_value=_FAKE_AI_RESULT),
    ):
        chat = client.post(
            "/public/v1/chat",
            json={"api_key": api_key, "message": "hello"},
        )
    assert chat.status_code == 200, chat.text


def test_pause_requires_published_status(client):
    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={"name": "Draft Bot", "system_prompt_template": "hi", "web_config": {}},
        headers=headers,
    )
    agent = resp.json()

    paused = client.post(f"/api/v1/agents/{agent['id']}/pause", headers=headers)
    assert paused.status_code == 409


def test_quota_exceeded_returns_429(client, db_session):
    from app.agent_platform.models.quota import CompanyQuota

    headers, company_id = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers)
    api_key = pub["api_key"]

    db_session.add(
        CompanyQuota(
            company_id=UUID(company_id),
            monthly_spend_limit=0,
            current_spend=0,
            monthly_token_limit=1_000_000,
            current_tokens=0,
        )
    )
    db_session.commit()

    resp = client.post(
        "/public/v1/chat",
        json={"api_key": api_key, "message": "hello"},
    )
    assert resp.status_code == 429
    assert resp.json()["error"] == "quota_exceeded"


def test_public_chat_by_slug_resolves_agent(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers, name="Slug Bot")
    api_key = pub["api_key"]
    slug = agent["slug"]
    assert slug

    with patch(
        "app.agent_platform.routers.public_router.AIGatewayService.process_request",
        new=AsyncMock(return_value=_FAKE_AI_RESULT),
    ):
        resp = client.post(
            f"/public/v1/agents/{slug}/chat",
            json={"api_key": api_key, "message": "hi"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reply"] == "Hello from AI"


def test_public_chat_by_slug_rejects_mismatched_key(client, db_session):
    from uuid import UUID

    from app.companies.model import Company, CompanyPlan

    headers, company_id = _auth(client)
    # Free plan caps agents_count at 1 — this test needs two agents in one company.
    company = db_session.query(Company).filter(Company.id == UUID(company_id)).one()
    company.plan = CompanyPlan.STARTER
    db_session.commit()

    agent_a, pub_a = _create_and_publish_agent(client, headers, name="Agent A")
    agent_b, pub_b = _create_and_publish_agent(client, headers, name="Agent B")

    resp = client.post(
        f"/public/v1/agents/{agent_b['slug']}/chat",
        json={"api_key": pub_a["api_key"], "message": "hi"},
    )
    assert resp.status_code == 403


def test_public_chat_by_slug_unknown_slug_404(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers)

    resp = client.post(
        "/public/v1/agents/does-not-exist/chat",
        json={"api_key": pub["api_key"], "message": "hi"},
    )
    assert resp.status_code == 404
