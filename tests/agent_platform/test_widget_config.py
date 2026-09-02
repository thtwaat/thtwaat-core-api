"""Tests for GET /public/v1/agents/{slug}/widget-config — the public,
capability-aware config endpoint the widget fetches once on init.

Covers: capability flags round-trip, API-key requirement, company isolation
(slug is only unique per company, not globally), and a recursive assertion
that nothing sensitive (system prompt, credentials, internal ids) is ever
present in the response body.
"""
from __future__ import annotations

import uuid


def _auth(client, role: str = "company_owner"):
    company_slug = f"wcfg-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Widget Cfg Co {company_slug}", "slug": company_slug},
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


def _create_and_publish_agent(client, headers, web_config, name: str, system_prompt: str):
    resp = client.post(
        "/v2/agents",
        json={
            "name": name,
            "system_prompt_template": system_prompt,
            "web_config": web_config,
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    agent = resp.json()
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return agent, pub.json()


FORBIDDEN_KEYS = {
    "system_prompt_template",
    "system_prompt",
    "provider",
    "model",
    "allowed_tools",
    "api_key",
    "key_hash",
    "company_id",
    "secret",
    "credentials",
}


def _collect_keys(obj) -> set:
    keys: set = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _collect_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _collect_keys(item)
    return keys


def test_widget_config_requires_api_key(client):
    headers, _ = _auth(client)
    agent, _pub = _create_and_publish_agent(
        client, headers, {}, "No Key Bot", "You are helpful. SECRET_INSTRUCTIONS_MARKER"
    )
    resp = client.get(f"/public/v1/agents/{agent['slug']}/widget-config")
    assert resp.status_code == 401


def test_widget_config_returns_selected_capabilities(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(
        client,
        headers,
        {"capabilities": {"voice": True, "vision": True, "image_generation": False, "calling": False}},
        "Caps Widget Bot",
        "You are helpful. SECRET_INSTRUCTIONS_MARKER",
    )
    api_key = pub["api_key"]
    slug = agent["slug"]

    resp = client.get(
        f"/public/v1/agents/{slug}/widget-config",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    caps = body["capabilities"]
    assert caps["voice"] is True
    assert caps["vision"] is True
    assert caps["image_generation"] is False
    assert caps["calling"] is False
    # Defaults for capabilities not explicitly configured.
    assert caps["memory"] is True
    assert caps["handoff"] is True
    assert caps["knowledge"] is True
    assert caps["lead_capture"] is True
    assert caps["multilingual"] is True
    assert caps["tools"] is False

    assert body["agent_name"] == "Caps Widget Bot"
    assert body["slug"] == slug
    assert "public_chat_url" in body


def test_widget_config_rejects_key_for_a_different_agent(client):
    headers, _ = _auth(client)
    agent_a, pub_a = _create_and_publish_agent(client, headers, {}, "Agent A", "You are A.")
    agent_b, pub_b = _create_and_publish_agent(client, headers, {}, "Agent B", "You are B.")

    resp = client.get(
        f"/public/v1/agents/{agent_b['slug']}/widget-config",
        headers={"Authorization": f"Bearer {pub_a['api_key']}"},
    )
    assert resp.status_code == 403


def test_widget_config_company_isolation_by_slug(client):
    """Slug is only unique per company. Company B's key must never resolve
    company A's same-slug agent, and must never leak any of its data."""
    headers_a, _ = _auth(client)
    agent_a, _pub_a = _create_and_publish_agent(
        client, headers_a, {}, "Iso Bot", "You are A. SECRET_COMPANY_A_MARKER"
    )

    headers_b, _ = _auth(client)
    agent_b, pub_b = _create_and_publish_agent(
        client, headers_b, {}, "Other Bot", "You are B. SECRET_COMPANY_B_MARKER"
    )

    # Company B's key, but requesting company A's slug -> not found, not a
    # cross-tenant peek at company A's config.
    resp = client.get(
        f"/public/v1/agents/{agent_a['slug']}/widget-config",
        headers={"Authorization": f"Bearer {pub_b['api_key']}"},
    )
    assert resp.status_code in (403, 404)
    assert "SECRET_COMPANY_A_MARKER" not in resp.text

    # Sanity: company B's own key + own slug still works normally.
    ok = client.get(
        f"/public/v1/agents/{agent_b['slug']}/widget-config",
        headers={"Authorization": f"Bearer {pub_b['api_key']}"},
    )
    assert ok.status_code == 200


def test_widget_config_same_slug_collision_across_companies_stays_isolated(client):
    """Two different companies naming their agent identically get the exact
    same slug string (slug is de-duped per-company only, see
    agent_router._unique_slug). Company A's key must resolve strictly to
    company A's agent/config for that slug — never company B's, even though
    the slug string itself collides."""
    headers_a, _ = _auth(client)
    agent_a, pub_a = _create_and_publish_agent(
        client,
        headers_a,
        {"capabilities": {"voice": True}},
        "Collision Bot",
        "You are Company A's bot. SECRET_A_ONLY_MARKER",
    )

    headers_b, _ = _auth(client)
    agent_b, pub_b = _create_and_publish_agent(
        client,
        headers_b,
        {"capabilities": {"voice": False}},
        "Collision Bot",
        "You are Company B's bot. SECRET_B_ONLY_MARKER",
    )

    # Both agents really do share the same slug string.
    assert agent_a["slug"] == agent_b["slug"]
    slug = agent_a["slug"]

    resp_a = client.get(
        f"/public/v1/agents/{slug}/widget-config",
        headers={"Authorization": f"Bearer {pub_a['api_key']}"},
    )
    assert resp_a.status_code == 200, resp_a.text
    body_a = resp_a.json()
    assert body_a["agent_name"] == "Collision Bot"
    assert body_a["capabilities"]["voice"] is True
    assert "SECRET_B_ONLY_MARKER" not in resp_a.text

    resp_b = client.get(
        f"/public/v1/agents/{slug}/widget-config",
        headers={"Authorization": f"Bearer {pub_b['api_key']}"},
    )
    assert resp_b.status_code == 200, resp_b.text
    body_b = resp_b.json()
    assert body_b["capabilities"]["voice"] is False
    assert "SECRET_A_ONLY_MARKER" not in resp_b.text

    # Cross-tenant: company B's key must never resolve to company A's row
    # for the identical slug, and company A's key never used at all here —
    # only B's key against the shared slug string, confirming the lookup is
    # scoped by (slug, api_key.company_id), never a global slug lookup.
    assert pub_a["api_key"] != pub_b["api_key"]


def test_widget_config_never_leaks_sensitive_fields(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(
        client,
        headers,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "capabilities": {"voice": True},
        },
        "Secure Bot",
        "SECRET_SYSTEM_PROMPT_MARKER — never expose this to visitors.",
    )
    api_key = pub["api_key"]

    resp = client.get(
        f"/public/v1/agents/{agent['slug']}/widget-config",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # No forbidden key anywhere in the response, at any nesting depth.
    assert FORBIDDEN_KEYS.isdisjoint(_collect_keys(body))

    # No sensitive value leaked either, independent of key names.
    assert "SECRET_SYSTEM_PROMPT_MARKER" not in resp.text
    assert api_key not in resp.text
    assert str(agent["company_id"]) not in resp.text
