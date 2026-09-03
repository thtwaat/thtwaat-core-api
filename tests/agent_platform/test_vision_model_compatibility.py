"""Tests for the Vision <-> Model compatibility validation added to Agent
create/update (config-save-time), plus the read-only vision-capable-models
catalog endpoint the Agent Builder UI uses to disable incompatible models.

Companion to test_vision_chat.py, which covers the pre-existing *runtime*
(request-time) gate — this file covers the *config-save-time* gate layered
in front of it. Both reuse the same VISION_CAPABLE_MODELS /
provider_model_supports_vision source of truth in app.agent_platform.agent_runtime.
"""
from __future__ import annotations

import uuid


def _auth(client, role: str = "company_owner"):
    company_slug = f"visioncfg-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Vision Cfg Co {company_slug}", "slug": company_slug},
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


def test_create_vision_true_with_vision_capable_model_is_accepted(client):
    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Vision OK Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "capabilities": {"vision": True},
            },
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()
    assert agent["web_config"]["capabilities"]["vision"] is True
    assert agent["web_config"]["model"] == "gpt-4o-mini"


def test_create_vision_true_with_incompatible_model_is_rejected(client):
    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Vision Bad Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "capabilities": {"vision": True},
            },
        },
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "Vision requires a vision-capable model" in resp.json()["error"]


def test_create_vision_false_with_any_model_is_unchanged_and_accepted(client):
    """vision=false must behave exactly as before this feature existed —
    no model restriction at all."""
    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={
            "name": "No Vision Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "capabilities": {"vision": False},
            },
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()
    assert agent["web_config"]["model"] == "gpt-3.5-turbo"
    assert agent["web_config"]["capabilities"]["vision"] is False


def test_update_enabling_vision_on_incompatible_model_is_rejected(client):
    headers, _ = _auth(client)
    created = client.post(
        "/v2/agents",
        json={
            "name": "Will Enable Vision",
            "system_prompt_template": "You are helpful.",
            "web_config": {"provider": "openai", "model": "gpt-3.5-turbo"},
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    agent = created.json()

    patch = client.patch(
        f"/v2/agents/{agent['id']}",
        json={"web_config": {"capabilities": {"vision": True}}},
        headers=headers,
    )
    assert patch.status_code == 400, patch.text
    assert "Vision requires a vision-capable model" in patch.json()["error"]

    # Rejected request must not have silently changed provider/model — refetch
    # and confirm the agent is exactly as it was created.
    refetched = client.get(f"/v2/agents/{agent['id']}", headers=headers)
    assert refetched.status_code == 200, refetched.text
    assert refetched.json()["web_config"]["model"] == "gpt-3.5-turbo"
    assert refetched.json()["web_config"].get("capabilities", {}).get("vision", False) is False


def test_update_preserves_provider_model_when_compatible(client):
    """An update that doesn't touch provider/model must leave them exactly as
    they were — no silent substitution — while still passing validation
    because they were already vision-compatible."""
    headers, _ = _auth(client)
    created = client.post(
        "/v2/agents",
        json={
            "name": "Stable Model Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "capabilities": {"vision": True},
            },
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    agent = created.json()

    patch = client.patch(
        f"/v2/agents/{agent['id']}",
        json={"description": "Just a description change"},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    updated = patch.json()
    assert updated["description"] == "Just a description change"
    assert updated["web_config"]["model"] == "gpt-4o-mini"
    assert updated["web_config"]["provider"] == "openai"
    assert updated["web_config"]["capabilities"]["vision"] is True


def test_existing_agent_with_vision_on_incompatible_model_surfaces_on_next_update(client, db_session):
    """An agent that somehow already has vision=true on an incompatible model
    (e.g. created before this validation existed) must not be silently left
    broken nor silently fixed — the next save attempt must surface the
    problem clearly rather than persisting it again."""
    from app.agent_platform.models.agent import AgentConfig

    headers, company_id = _auth(client)
    created = client.post(
        "/v2/agents",
        json={
            "name": "Legacy Broken Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {"provider": "openai", "model": "gpt-3.5-turbo"},
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    agent_id = created.json()["id"]

    # Simulate a pre-existing broken row by writing directly to the DB,
    # bypassing the new validation entirely (as an old row created before
    # this feature shipped would already be).
    row = db_session.query(AgentConfig).filter(AgentConfig.id == agent_id).first()
    web_config = dict(row.web_config or {})
    web_config["capabilities"] = {**web_config.get("capabilities", {}), "vision": True}
    row.web_config = web_config
    db_session.add(row)
    db_session.commit()

    patch = client.patch(
        f"/v2/agents/{agent_id}",
        json={"description": "Trying to save"},
        headers=headers,
    )
    assert patch.status_code == 400, patch.text
    assert "Vision requires a vision-capable model" in patch.json()["error"]


def test_vision_capable_models_endpoint_reuses_runtime_table(client):
    from app.agent_platform.agent_runtime import VISION_CAPABLE_MODELS

    headers, _ = _auth(client)
    resp = client.get("/v2/agents/vision-capable-models", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "openai" in body
    assert set(body["openai"]) == set(VISION_CAPABLE_MODELS["openai"])


def test_runtime_image_request_still_uses_existing_vision_gating(client):
    """The request-time AgentRuntime gate (app.agent_platform.agent_runtime.
    AgentRuntime.check_vision_request) must remain the final safety layer,
    unchanged and untouched by the new config-save-time validation."""
    from unittest.mock import AsyncMock, patch as mock_patch

    from app.agent_platform.schemas import UnifiedChatResponse

    headers, _ = _auth(client)
    # A vision-enabled, vision-capable agent created through the normal path
    # (passes the new config-save-time gate) must still be independently
    # gated at request time by the untouched runtime check.
    created = client.post(
        "/v2/agents",
        json={
            "name": "Runtime Gate Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "capabilities": {"vision": True},
            },
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    pub = client.post(f"/api/v1/agents/{created.json()['id']}/publish", headers=headers)
    assert pub.status_code == 200, pub.text

    fake_response = UnifiedChatResponse(
        content="I see a picture.",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )
    mock_call = AsyncMock(return_value=fake_response)
    with mock_patch(
        "app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call
    ):
        resp = client.post(
            "/public/v1/chat",
            json={
                "api_key": pub.json()["api_key"],
                "message": "what's in this?",
                "images": [{"type": "image_url", "image_url": {"url": "https://example.com/x.png"}}],
            },
        )
    assert resp.status_code == 200, resp.text
    assert mock_call.call_count == 1


def test_calling_false_does_not_expose_calling_functionality(client):
    """Regression guard: calling=false must continue hiding/disabling calling
    behavior — unchanged by this feature, which never touches calling."""
    from app.agent_platform.agent_runtime import AgentRuntime, agent_capabilities
    from fastapi import HTTPException
    import pytest

    caps = agent_capabilities({"capabilities": {"calling": False}})
    assert caps["calling"] is False
    with pytest.raises(HTTPException) as exc_info:
        AgentRuntime.check_calling_request(caps)
    assert exc_info.value.status_code == 400
