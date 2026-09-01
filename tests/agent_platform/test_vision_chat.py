"""Tests for the vision (image input) capability: authorization gate and end-to-end shape."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from app.agent_platform.schemas import UnifiedChatResponse

_IMAGE_BLOCK = {"type": "image_url", "image_url": {"url": "https://example.com/x.png"}}


def _auth(client, role: str = "company_owner"):
    company_slug = f"vision-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Vision Co {company_slug}", "slug": company_slug},
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


def _create_and_publish_agent(client, headers, web_config):
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Vision Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": web_config,
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return agent, pub.json()


_FAKE = UnifiedChatResponse(
    content="I see a picture.",
    provider="openai",
    model="gpt-4o-mini",
    input_tokens=10,
    output_tokens=5,
    total_tokens=15,
)


def test_vision_disabled_agent_rejects_image(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(
        client, headers, {"provider": "openai", "model": "gpt-4o-mini"}
    )

    mock_call = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call):
        resp = client.post(
            "/public/v1/chat",
            json={"api_key": pub["api_key"], "message": "what's in this?", "images": [_IMAGE_BLOCK]},
        )
    assert resp.status_code == 400, resp.text
    assert "vision capability" in resp.json()["detail"]
    assert mock_call.call_count == 0


def test_vision_enabled_but_non_vision_model_rejects_image(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(
        client,
        headers,
        {"provider": "openai", "model": "gpt-3.5-turbo", "capabilities": {"vision": True}},
    )

    mock_call = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call):
        resp = client.post(
            "/public/v1/chat",
            json={"api_key": pub["api_key"], "message": "what's in this?", "images": [_IMAGE_BLOCK]},
        )
    assert resp.status_code == 400, resp.text
    assert "does not support image input" in resp.json()["detail"]
    assert mock_call.call_count == 0


def test_vision_enabled_openai_gpt4o_accepts_image(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(
        client,
        headers,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"vision": True}},
    )

    mock_call = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call):
        resp = client.post(
            "/public/v1/chat",
            json={"api_key": pub["api_key"], "message": "what's in this?", "images": [_IMAGE_BLOCK]},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reply"] == "I see a picture."
    assert mock_call.call_count == 1

    sent_request = mock_call.call_args.args[0]
    last_message = sent_request.messages[-1]
    assert last_message["role"] == "user"
    assert isinstance(last_message["content"], list)
    assert last_message["content"][0] == {"type": "text", "text": "what's in this?"}
    assert last_message["content"][1] == _IMAGE_BLOCK


def test_vision_dashboard_endpoint_same_gate(client):
    headers, _ = _auth(client)

    # Vision-disabled agent, dashboard endpoint.
    agent, _ = _create_and_publish_agent(
        client, headers, {"provider": "openai", "model": "gpt-4o-mini"}
    )
    mock_call = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call):
        resp = client.post(
            f"/v2/agents/{agent['id']}/chat",
            json={"message": "what's in this?", "images": [_IMAGE_BLOCK]},
            headers=headers,
        )
    assert resp.status_code == 400, resp.text
    assert mock_call.call_count == 0

    # Vision-enabled OpenAI gpt-4o agent, dashboard endpoint.
    agent2, _ = _create_and_publish_agent(
        client,
        headers,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"vision": True}},
    )
    mock_call2 = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call2):
        resp2 = client.post(
            f"/v2/agents/{agent2['id']}/chat",
            json={"message": "what's in this?", "images": [_IMAGE_BLOCK]},
            headers=headers,
        )
    assert resp2.status_code == 200, resp2.text
    assert mock_call2.call_count == 1
    sent_request = mock_call2.call_args.args[0]
    assert isinstance(sent_request.messages[-1]["content"], list)


def test_vision_cross_company_isolation_still_holds(client):
    headers_a, _ = _auth(client)
    headers_b, _ = _auth(client)
    agent_a, pub_a = _create_and_publish_agent(
        client,
        headers_a,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"vision": True}},
    )
    _, pub_b = _create_and_publish_agent(
        client,
        headers_b,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"vision": True}},
    )

    # Company B's key must not be able to chat with company A's agent, even
    # for an ordinary text request — vision plumbing must not weaken this.
    resp = client.post(
        f"/public/v1/agents/{agent_a['slug']}/chat",
        json={"api_key": pub_b["api_key"], "message": "hi", "images": [_IMAGE_BLOCK]},
    )
    assert resp.status_code in (403, 404), resp.text


def test_existing_agents_without_vision_key_unaffected(client):
    """Regression guard: an agent shaped like Viral Awaaz (no capabilities key at
    all) must behave identically to before — plain string content, no gate."""
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers, {"provider": "openai", "model": "gpt-4o-mini"})

    mock_call = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call):
        resp = client.post(
            "/public/v1/chat",
            json={"api_key": pub["api_key"], "message": "plain text only, no images"},
        )
    assert resp.status_code == 200, resp.text
    assert mock_call.call_count == 1
    sent_request = mock_call.call_args.args[0]
    assert isinstance(sent_request.messages[-1]["content"], str)

    mock_call2 = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call2):
        resp2 = client.post(
            f"/v2/agents/{agent['id']}/chat",
            json={"message": "plain text only, no images"},
            headers=headers,
        )
    assert resp2.status_code == 200, resp2.text
    sent_request2 = mock_call2.call_args.args[0]
    assert isinstance(sent_request2.messages[-1]["content"], str)


def test_vision_sse_stream_endpoint_error_shape(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers, {"provider": "openai", "model": "gpt-4o-mini"})

    mock_call = AsyncMock(return_value=_FAKE)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call):
        resp = client.post(
            "/public/v1/chat/stream",
            json={"api_key": pub["api_key"], "message": "what's in this?", "images": [_IMAGE_BLOCK]},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "event: error" in body
    assert "vision capability" in body
    assert mock_call.call_count == 0
