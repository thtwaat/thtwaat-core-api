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
    headers, _ = _auth(client, role="company_owner")
    agent = _create_agent(client, headers)

    resp = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "PUBLISHED"
    assert data["agent_id"] == agent["id"]
    assert data["api_key"].startswith("tht_live_")
    assert "YOUR_KEY" not in data["api_key"]
    assert data["widget_id"].startswith("wgt_")
    assert "/public/v1/chat" in data["public_chat_url"]
    assert "widget.js" in data["embed_script"]
    assert f'data-api-key="{data["api_key"]}"' in data["embed_script"]
    assert "YOUR_KEY" not in data["embed_script"]
    assert "/public/v1/widget/embed" in data["iframe_url"]
    assert "api_key=" not in data["iframe_url"]
    assert "tht_live_" not in data["iframe_url"]
    assert f"widget_id={data['widget_id']}" in data["iframe_url"]
    assert "embed_token=" in data["iframe_url"]

    embed_page = client.get(data["iframe_url"])
    assert embed_page.status_code == 200, embed_page.text
    assert "api_key=" not in str(embed_page.url)
    assert "tht_live_" not in embed_page.text
    assert "tht_embed_" in embed_page.text
    assert data["widget_id"] in embed_page.text

    # Widget config lookup by widget_id (Option A/B public config).
    cfg = client.get(f"/public/v1/widget/{data['widget_id']}")
    assert cfg.status_code == 200, cfg.text
    assert cfg.json()["widget_id"] == data["widget_id"]
    assert cfg.json()["status"] == "PUBLISHED"


def test_publish_reuses_existing_key_when_plaintext_known(client):
    """Generate-then-publish path: existing active key + known plaintext → no duplicate."""
    from uuid import UUID

    from app.agent_platform.models.api_key import AgentApiKey
    from app.agent_platform.publish.service import PublishService, hash_api_key
    from app.database.database import get_db
    from app.users.model import User

    headers, company_id = _auth(client, role="company_owner")
    agent = _create_agent(client, headers)

    created = client.post(
        f"/api/v1/agents/{agent['id']}/api-keys",
        json={"name": "Pre-publish Key"},
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    known = created.json()["api_key"]
    assert known.startswith("tht_live_")

    db = next(get_db())
    user = db.query(User).filter(User.company_id == UUID(company_id)).first()
    assert user is not None
    pub = PublishService(db).publish(
        UUID(agent["id"]),
        UUID(company_id),
        user.id,
        known_api_key=known,
    )
    assert pub.api_key == known
    assert "YOUR_KEY" not in pub.embed_script
    assert f'data-api-key="{known}"' in pub.embed_script

    active = (
        db.query(AgentApiKey)
        .filter(
            AgentApiKey.agent_id == UUID(agent["id"]),
            AgentApiKey.is_active.is_(True),
            AgentApiKey.revoked_at.is_(None),
        )
        .all()
    )
    assert len(active) == 1
    assert active[0].key_hash == hash_api_key(known)


def test_publish_reissues_key_when_existing_plaintext_unavailable(client):
    headers, _company_id = _auth(client, role="company_owner")
    agent = _create_agent(client, headers)

    created = client.post(
        f"/api/v1/agents/{agent['id']}/api-keys",
        json={"name": "Hidden Key"},
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    old_key = created.json()["api_key"]

    resp = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["api_key"].startswith("tht_live_")
    assert data["api_key"] != old_key
    assert "YOUR_KEY" not in data["embed_script"]
    assert f'data-api-key="{data["api_key"]}"' in data["embed_script"]

    keys = client.get(f"/api/v1/agents/{agent['id']}/api-keys", headers=headers)
    assert keys.status_code == 200
    active = [k for k in keys.json() if k.get("is_active")]
    assert len(active) == 1


def test_iframe_embed_rejects_live_api_key_in_url(client):
    headers, _ = _auth(client, role="company_owner")
    agent = _create_agent(client, headers)
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200
    live_key = pub.json()["api_key"]

    resp = client.get(f"/public/v1/widget/embed?api_key={live_key}")
    assert resp.status_code == 400
    assert "iframe" in resp.text.lower() or "embed" in resp.text.lower()


def test_iframe_embed_rejects_invalid_token(client):
    resp = client.get(
        "/public/v1/widget/embed?widget_id=wgt_missing&embed_token=not-valid"
    )
    assert resp.status_code == 401


def test_iframe_embed_rejects_expired_token(client):
    from datetime import datetime, timedelta, timezone
    from urllib.parse import parse_qs, urlparse

    from jose import jwt

    from app.agent_platform.publish import embed_tokens
    from app.config.settings import settings

    headers, _ = _auth(client, role="company_owner")
    agent = _create_agent(client, headers)
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200
    widget_id = pub.json()["widget_id"]

    qs = parse_qs(urlparse(pub.json()["iframe_url"]).query)
    good = qs["embed_token"][0]
    claims = jwt.decode(good, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    past = datetime.now(timezone.utc) - timedelta(hours=3)
    expired = embed_tokens.mint_embed_token(
        widget_id=widget_id,
        agent_id=claims["aid"],
        company_id=claims["cid"],
        ttl_seconds=60,
        now=past,
    )
    resp = client.get(
        f"/public/v1/widget/embed?widget_id={widget_id}&embed_token={expired}"
    )
    assert resp.status_code == 401


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
