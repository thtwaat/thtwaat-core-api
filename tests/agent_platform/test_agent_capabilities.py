"""Tests for agent capability persistence via /v2/agents and the web_config
merge-safety fix in ``agent_router.update_agent``.

A capability-only PATCH (e.g. from the Agent Edit "Capabilities" card, which
sends ``{"web_config": {"capabilities": {...}}}``) must not silently erase
unrelated ``web_config`` sections such as ``widget``, ``voice``, ``provider``.
"""
from __future__ import annotations

import uuid


def _auth(client, role: str = "company_owner"):
    company_slug = f"caps-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Caps Co {company_slug}", "slug": company_slug},
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


def test_capability_flags_persist_through_create_and_update(client):
    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Caps Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {"capabilities": {"voice": True, "vision": False}},
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()
    assert agent["web_config"]["capabilities"]["voice"] is True
    assert agent["web_config"]["capabilities"]["vision"] is False

    patch = client.patch(
        f"/v2/agents/{agent['id']}",
        json={"web_config": {"capabilities": {"voice": False, "image_generation": True}}},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    updated = patch.json()
    assert updated["web_config"]["capabilities"]["voice"] is False
    assert updated["web_config"]["capabilities"]["image_generation"] is True


def test_agent_with_no_capabilities_configured_resolves_safe_defaults(client):
    """An agent created with an empty web_config (or none of the new keys)
    must behave exactly as it did before this feature existed."""
    from app.agent_platform.agent_runtime import agent_capabilities

    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={"name": "Plain Bot", "system_prompt_template": "You are helpful."},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()
    assert agent["web_config"] == {}

    caps = agent_capabilities(agent["web_config"])
    assert caps["voice"] is False
    assert caps["vision"] is False
    assert caps["calling"] is False
    assert caps["image_generation"] is False
    assert caps["knowledge"] is True
    assert caps["memory"] is True
    assert caps["handoff"] is True


def test_capability_only_update_preserves_unrelated_web_config_keys(client):
    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Merge Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "routing": "explicit",
                "widget": {"theme": "dark", "primary_color": "#123456"},
                "voice": {"provider": "openai", "voice_id": "alloy"},
                "calling": {"provider": "twilio", "phone_number": "+15551234567"},
                "capabilities": {"voice": False, "handoff": True},
            },
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()

    patch = client.patch(
        f"/v2/agents/{agent['id']}",
        json={"web_config": {"capabilities": {"voice": True, "handoff": True}}},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    updated = patch.json()["web_config"]

    # The capability change landed...
    assert updated["capabilities"]["voice"] is True
    assert updated["capabilities"]["handoff"] is True
    # ...and every other web_config section survived untouched.
    assert updated["provider"] == "openai"
    assert updated["model"] == "gpt-4o-mini"
    assert updated["routing"] == "explicit"
    assert updated["widget"]["theme"] == "dark"
    assert updated["widget"]["primary_color"] == "#123456"
    assert updated["voice"]["voice_id"] == "alloy"
    assert updated["calling"]["phone_number"] == "+15551234567"


def test_non_web_config_update_is_unaffected_by_merge_change(client):
    """Sanity check: PATCH bodies that omit web_config entirely (the common
    case — name/description/provider edits) keep behaving exactly as before."""
    headers, _ = _auth(client)
    resp = client.post(
        "/v2/agents",
        json={
            "name": "Untouched Bot",
            "system_prompt_template": "You are helpful.",
            "web_config": {"capabilities": {"voice": True}},
        },
        headers=headers,
    )
    agent = resp.json()

    patch = client.patch(
        f"/v2/agents/{agent['id']}",
        json={"description": "Updated description"},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    updated = patch.json()
    assert updated["description"] == "Updated description"
    assert updated["web_config"]["capabilities"]["voice"] is True
