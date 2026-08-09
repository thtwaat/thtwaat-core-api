"""Tests for tool-calling: registration, schema building, authorization, and execution."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

import app.agent_platform.tools.knowledge_search  # noqa: F401 — self-registers with ToolRegistry
from app.agent_platform.agent_runtime import build_tool_schemas
from app.agent_platform.registries.tool_registry import ToolRegistry
from app.agent_platform.schemas import UnifiedChatResponse


def _auth(client, role: str = "company_owner"):
    company_slug = f"tools-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Tools Co {company_slug}", "slug": company_slug},
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


def _create_and_publish_agent(client, headers, allowed_tools=None):
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Tool Bot",
            "system_prompt_template": "You are helpful.",
            "allowed_tools": allowed_tools or [],
            "web_config": {"provider": "openai", "model": "gpt-4o-mini"},
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return agent, pub.json()


@pytest.mark.unit
def test_knowledge_search_tool_is_registered():
    assert "knowledge_search" in ToolRegistry.list_tools()
    tool = ToolRegistry.get_tool("knowledge_search")
    assert tool.name == "knowledge_search"
    assert "query" in tool.schema["properties"]


@pytest.mark.unit
def test_build_tool_schemas_openai_shape():
    schemas = build_tool_schemas(["knowledge_search"])
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "knowledge_search"
    assert "query" in schemas[0]["function"]["parameters"]["properties"]


def test_agent_without_allowed_tools_never_sends_tools_payload(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers, allowed_tools=[])

    fake = UnifiedChatResponse(
        content="Plain answer",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
    )
    mock_call = AsyncMock(return_value=fake)
    with patch(
        "app.agent_platform.gateway.service.AIGatewayService.process_request",
        new=mock_call,
    ):
        resp = client.post(
            "/public/v1/chat",
            json={"api_key": pub["api_key"], "message": "hi"},
        )
    assert resp.status_code == 200, resp.text
    assert mock_call.call_count == 1
    sent_request = mock_call.call_args.args[0]
    assert sent_request.tools is None


def test_agent_with_allowed_tools_executes_tool_call_and_makes_one_followup(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers, allowed_tools=["knowledge_search"])

    tool_call_response = UnifiedChatResponse(
        content="",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=5,
        output_tokens=5,
        total_tokens=10,
        finish_reason="tool_calls",
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "knowledge_search", "arguments": '{"query": "refund policy"}'},
            }
        ],
    )
    final_response = UnifiedChatResponse(
        content="Here is our refund policy.",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=8,
        output_tokens=6,
        total_tokens=14,
    )
    canned = iter([tool_call_response, final_response])
    seen_requests = []

    async def fake_process_request(request, *args, **kwargs):
        # chat_request is mutated in place between calls — snapshot its shape now,
        # not a reference to the (later-mutated) object.
        seen_requests.append(
            {
                "tools": None if request.tools is None else list(request.tools),
                "roles": [m["role"] for m in request.messages],
            }
        )
        return next(canned)

    with patch(
        "app.agent_platform.gateway.service.AIGatewayService.process_request",
        new=AsyncMock(side_effect=fake_process_request),
    ), patch(
        "app.agent_platform.tools.knowledge_search.KnowledgeSearchTool.execute",
        new=AsyncMock(return_value="No relevant knowledge found."),
    ):
        resp = client.post(
            "/public/v1/chat",
            json={"api_key": pub["api_key"], "message": "What's your refund policy?"},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["reply"] == "Here is our refund policy."
    assert len(seen_requests) == 2

    first_request = seen_requests[0]
    assert first_request["tools"] is not None
    assert first_request["tools"][0]["function"]["name"] == "knowledge_search"

    second_request = seen_requests[1]
    assert second_request["tools"] is None
    assert "tool" in second_request["roles"]
