"""Tests for the dashboard single-shot chat endpoint, usage-tracking fix, and multi-KB search."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch
from uuid import UUID

from app.agent_platform.agent_runtime import search_agent_knowledge
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase, KnowledgeBaseAgent
from app.agent_platform.knowledge.schemas import SearchResult
from app.agent_platform.schemas import UnifiedChatResponse
from app.usage.models import UsageEvent


def _auth(client, role: str = "company_owner"):
    company_slug = f"dashchat-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Dash Chat Co {company_slug}", "slug": company_slug},
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
    user_id = user_resp.json()["id"]

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id, user_id


def _create_agent(client, headers):
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Dash Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {"provider": "openai", "model": "gpt-4o-mini"},
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


_FAKE = UnifiedChatResponse(
    content="Dashboard reply",
    provider="openai",
    model="gpt-4o-mini",
    input_tokens=3,
    output_tokens=4,
    total_tokens=7,
)


def test_agent_chat_endpoint_auto_creates_conversation(client):
    headers, _, _ = _auth(client)
    agent = _create_agent(client, headers)

    with patch(
        "app.agent_platform.gateway.service.AIGatewayService.process_request",
        new=AsyncMock(return_value=_FAKE),
    ):
        resp = client.post(
            f"/v2/agents/{agent['id']}/chat",
            json={"message": "hi there"},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["message"] == "Dashboard reply"
    assert data["conversation_id"]
    assert data["usage"]["total_tokens"] == 7

    # Sending again with the returned conversation_id continues the same thread.
    with patch(
        "app.agent_platform.gateway.service.AIGatewayService.process_request",
        new=AsyncMock(return_value=_FAKE),
    ):
        resp2 = client.post(
            f"/v2/agents/{agent['id']}/chat",
            json={"message": "follow up", "conversation_id": data["conversation_id"]},
            headers=headers,
        )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["conversation_id"] == data["conversation_id"]


def test_agent_chat_endpoint_company_isolated(client):
    headers_a, _, _ = _auth(client)
    headers_b, _, _ = _auth(client)
    agent = _create_agent(client, headers_a)

    resp = client.post(
        f"/v2/agents/{agent['id']}/chat",
        json={"message": "hi"},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_dashboard_chat_records_usage_event(client, db_session):
    headers, company_id, _ = _auth(client)
    agent = _create_agent(client, headers)

    before = (
        db_session.query(UsageEvent)
        .filter(UsageEvent.company_id == UUID(company_id), UsageEvent.source == "dashboard")
        .count()
    )

    # Mock one level below AIGatewayService.process_request (the provider adapter's
    # generate_response) so the real process_request body — including its
    # Tracker.log_usage(db=..., source="dashboard") call — actually executes.
    # Mocking process_request itself would skip that call entirely and prove nothing.
    with patch(
        "app.agent_platform.providers.openai.OpenAIProvider.generate_response",
        new=AsyncMock(return_value=_FAKE),
    ):
        resp = client.post(
            f"/v2/agents/{agent['id']}/chat",
            json={"message": "track me"},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text

    after = (
        db_session.query(UsageEvent)
        .filter(UsageEvent.company_id == UUID(company_id), UsageEvent.source == "dashboard")
        .count()
    )
    assert after > before, "dashboard chat should now record a UsageEvent (was previously silently skipped)"


def test_search_agent_knowledge_merges_across_multiple_kbs(client, db_session):
    headers, company_id, _ = _auth(client)
    agent = _create_agent(client, headers)
    agent_id = UUID(agent["id"])
    company_uuid = UUID(company_id)

    kb_a = KnowledgeBase(company_id=company_uuid, name="KB A")
    kb_b = KnowledgeBase(company_id=company_uuid, name="KB B")
    db_session.add_all([kb_a, kb_b])
    db_session.flush()
    db_session.add(KnowledgeBaseAgent(knowledge_base_id=kb_a.id, agent_id=agent_id))
    db_session.add(KnowledgeBaseAgent(knowledge_base_id=kb_b.id, agent_id=agent_id))
    db_session.commit()

    def fake_search(db, query, top_k, company_id, kb_id=None):
        if kb_id == kb_a.id:
            return [SearchResult(chunk_id="1", document_id="d1", document_name="A-doc", text="from A", score=0.5)]
        if kb_id == kb_b.id:
            return [SearchResult(chunk_id="2", document_id="d2", document_name="B-doc", text="from B", score=0.9)]
        return []

    with patch(
        "app.agent_platform.knowledge.services.KnowledgeService.search_knowledge_base",
        side_effect=fake_search,
    ):
        results = search_agent_knowledge(db_session, agent_id, "anything", company_uuid, top_k=5)

    assert [r.document_name for r in results] == ["B-doc", "A-doc"]  # ranked by score desc, both KBs represented
