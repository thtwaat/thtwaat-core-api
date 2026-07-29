"""Tests for Agent Publish Service."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest


def _auth(client, role: str = "admin"):
    company_slug = f"pub-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Publish Co", "slug": company_slug},
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


def _create_agent(client, headers):
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Publish Bot",
            "description": "test",
            "system_prompt_template": "You are a helpful assistant.",
            "temperature": 0.2,
            "web_config": {"provider": "openai", "model": "gpt-4o-mini"},
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_publish_agent_returns_embed_payload(client):
    headers, _ = _auth(client, role="admin")
    agent = _create_agent(client, headers)

    resp = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "PUBLISHED"
    assert data["agent_id"] == agent["id"]
    assert data["api_key"].startswith("tht_live_")
    assert data["widget_id"].startswith("wgt_")
    assert "/public/v1/chat" in data["public_chat_url"]
    assert "widget.js" in data["embed_script"]
    assert data["widget_id"] in data["iframe_url"]


def test_publish_forbidden_for_viewer(client):
    headers, _ = _auth(client, role="viewer")
    # viewers cannot create via v2 easily if no RBAC — create with admin then switch
    admin_headers, company_id = _auth(client, role="admin")
    agent = _create_agent(client, admin_headers)

    # create viewer in same company
    email = f"viewer-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "View",
            "last_name": "Er",
            "role": "viewer",
        },
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=viewer_headers)
    assert resp.status_code == 403


def test_unpublish_and_public_chat_blocked(client):
    headers, _ = _auth(client, role="company_owner")
    agent = _create_agent(client, headers)

    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200
    api_key = pub.json()["api_key"]

    unpub = client.post(f"/api/v1/agents/{agent['id']}/unpublish", headers=headers)
    assert unpub.status_code == 200
    assert unpub.json()["status"] == "DRAFT"

    chat = client.post(
        "/public/v1/chat",
        json={"api_key": api_key, "message": "hello"},
    )
    assert chat.status_code == 403


def test_api_key_rotate_and_list(client):
    headers, _ = _auth(client, role="admin")
    agent = _create_agent(client, headers)
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200

    keys = client.get(f"/api/v1/agents/{agent['id']}/api-keys", headers=headers)
    assert keys.status_code == 200
    assert len(keys.json()) >= 1
    key_id = keys.json()[0]["id"]

    rotated = client.post(
        f"/api/v1/agents/{agent['id']}/api-keys/{key_id}/rotate",
        headers=headers,
    )
    assert rotated.status_code == 200
    assert rotated.json()["api_key"].startswith("tht_live_")


def test_widget_config_and_widget_js(client):
    headers, _ = _auth(client, role="admin")
    agent = _create_agent(client, headers)
    client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)

    cfg = client.get(f"/api/v1/agents/{agent['id']}/widget", headers=headers)
    assert cfg.status_code == 200
    assert cfg.json()["config"]["position"] == "bottom-right"

    patched = client.patch(
        f"/api/v1/agents/{agent['id']}/widget",
        json={"primary_color": "#ff0000", "welcome_message": "Hello!"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["config"]["primary_color"] == "#ff0000"

    js = client.get("/widget.js")
    assert js.status_code == 200
    assert "data-api-key" in js.text


def test_public_chat_with_mock_ai(client):
    headers, _ = _auth(client, role="admin")
    agent = _create_agent(client, headers)
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    api_key = pub.json()["api_key"]

    fake = type(
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
        },
    )()

    with patch(
        "app.agent_platform.routers.public_router.AIGatewayService.process_request",
        new=AsyncMock(return_value=fake),
    ):
        resp = client.post(
            "/public/v1/chat",
            json={"api_key": api_key, "message": "hi", "session_id": None},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["reply"] == "Hello from AI"
    assert data["conversation_id"]
    assert data["usage"]["total_tokens"] == 3
