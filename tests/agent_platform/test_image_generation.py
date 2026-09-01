"""Tests for the image-generation capability: capability gate, provider/model
selection, AgentRuntime integration, conversation persistence, company
isolation, publish-status gating, usage recording, and provider-failure
handling.

The global HTTPException handler (app/api/exceptions.py) reshapes error
bodies to ``{"error": ..., "code": ...}`` (not FastAPI's default
``{"detail": ...}``) — assertions below match that actual shape, same as
tests/agent_platform/test_voice_chat.py.
"""
from __future__ import annotations

import base64
import uuid
from unittest.mock import AsyncMock, patch

from app.agent_platform.image_generation.schemas import ImageGenerationResult

_FAKE_IMAGE = ImageGenerationResult(
    image_bytes=b"FAKE_PNG_BYTES",
    mime_type="image/png",
    provider="openai",
    model="dall-e-3",
    revised_prompt="a fluffy orange cat wearing a tiny hat",
)


def _auth(client, role: str = "company_owner"):
    company_slug = f"img-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Image Co {company_slug}", "slug": company_slug},
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


def _create_agent(client, headers, web_config, name: str = "Image Bot"):
    resp = client.post(
        "/v2/agents",
        json={
            "name": name,
            "system_prompt_template": "You are helpful.",
            "web_config": web_config,
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def _publish(client, headers, agent_id):
    pub = client.post(f"/api/v1/agents/{agent_id}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return pub.json()


def _mock_provider(generate_return=None, side_effect=None):
    provider = AsyncMock()
    if side_effect is not None:
        provider.generate = AsyncMock(side_effect=side_effect)
    else:
        provider.generate = AsyncMock(return_value=generate_return or [_FAKE_IMAGE])
    return provider


def _patch_registry(provider):
    return patch(
        "app.agent_platform.image_generation.runtime.ImageGenerationProviderRegistry.get_provider",
        return_value=provider,
    )


_ENABLED_CFG = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "capabilities": {"image_generation": True},
}
_DISABLED_CFG = {"provider": "openai", "model": "gpt-4o-mini"}


# 1 & 3 — defaults false / disabled rejected -------------------------------


def test_image_generation_defaults_false_and_rejects(client):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _DISABLED_CFG)
    pub = _publish(client, headers, agent["id"])

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a cat"}
        )
    assert resp.status_code == 400, resp.text
    assert "image generation capability" in resp.json()["error"]
    assert provider.generate.call_count == 0


def test_image_generation_dashboard_same_gate(client):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _DISABLED_CFG)

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            f"/v2/agents/{agent['id']}/image", json={"prompt": "a cat"}, headers=headers
        )
    assert resp.status_code == 400, resp.text
    assert provider.generate.call_count == 0


# 2, 4, 5, 6, 7 — enabled roundtrip + provider/model selection + response shape


def test_image_generation_enabled_roundtrip_public(client):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _ENABLED_CFG)
    pub = _publish(client, headers, agent["id"])

    provider = _mock_provider()
    with _patch_registry(provider) as get_provider_mock:
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a cat in a hat"}
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["images"]) == 1
    img = body["images"][0]
    assert base64.b64decode(img["data_base64"]) == b"FAKE_PNG_BYTES"
    assert img["mime_type"] == "image/png"
    assert img["revised_prompt"] == "a fluffy orange cat wearing a tiny hat"
    assert img["provider"] == "openai"
    assert img["model"] == "dall-e-3"

    # Provider registry resolved with the agent's configured provider ("openai" default).
    get_provider_mock.assert_called_once()
    assert get_provider_mock.call_args.args[0] == "openai"

    # Model/size/quality passed straight from web_config.image_generation defaults.
    provider.generate.assert_awaited_once()
    call_kwargs = provider.generate.await_args.kwargs
    assert call_kwargs["model"] == "dall-e-3"
    assert call_kwargs["size"] == "1024x1024"
    assert call_kwargs["quality"] == "standard"
    assert provider.generate.await_args.args[0] == "a cat in a hat"


def test_image_generation_custom_config_selection(client):
    headers, _ = _auth(client)
    cfg = dict(_ENABLED_CFG)
    cfg["image_generation"] = {
        "provider": "openai",
        "model": "dall-e-2",
        "size": "512x512",
        "quality": "hd",
    }
    agent = _create_agent(client, headers, cfg)
    pub = _publish(client, headers, agent["id"])

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a dog"}
        )
    assert resp.status_code == 200, resp.text
    call_kwargs = provider.generate.await_args.kwargs
    assert call_kwargs["model"] == "dall-e-2"
    assert call_kwargs["size"] == "512x512"
    assert call_kwargs["quality"] == "hd"


def test_image_generation_dashboard_roundtrip_and_conversation_persists(client):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _ENABLED_CFG)

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            f"/v2/agents/{agent['id']}/image", json={"prompt": "a cat in a hat"}, headers=headers
        )
    assert resp.status_code == 200, resp.text
    conversation_id = resp.json()["conversation_id"]

    conv_resp = client.get(f"/v2/conversations/{conversation_id}", headers=headers)
    assert conv_resp.status_code == 200, conv_resp.text
    conv = conv_resp.json()
    assert conv["channel"] == "image"
    roles = [m["role"] for m in conv["messages"]]
    assert roles == ["user", "assistant"]
    assert conv["messages"][0]["content"] == "a cat in a hat"
    assert "fluffy orange cat" in conv["messages"][1]["content"]


# 17 — invalid configuration -------------------------------------------------


def test_image_generation_unsupported_model_rejected(client):
    headers, _ = _auth(client)
    cfg = dict(_ENABLED_CFG)
    cfg["image_generation"] = {"provider": "openai", "model": "not-a-real-model"}
    agent = _create_agent(client, headers, cfg)
    pub = _publish(client, headers, agent["id"])

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a cat"}
        )
    assert resp.status_code == 400, resp.text
    assert "does not support image generation" in resp.json()["error"]
    assert provider.generate.call_count == 0


# 9 — company isolation -------------------------------------------------------


def test_image_generation_cross_company_isolation(client):
    headers_a, _ = _auth(client)
    headers_b, _ = _auth(client)
    agent_a = _create_agent(client, headers_a, _ENABLED_CFG, name="Image Bot Company A")
    pub_a = _publish(client, headers_a, agent_a["id"])
    _agent_b = _create_agent(client, headers_b, _ENABLED_CFG, name="Image Bot Company B")
    pub_b = _publish(client, headers_b, _agent_b["id"])

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            f"/public/v1/agents/{agent_a['slug']}/image",
            json={"api_key": pub_b["api_key"], "prompt": "a cat"},
        )
    assert resp.status_code in (403, 404), resp.text
    assert provider.generate.call_count == 0


# 10 — RBAC (dashboard requires auth) -----------------------------------------


def test_image_generation_dashboard_requires_auth(client):
    resp = client.post(
        "/v2/agents/00000000-0000-0000-0000-000000000000/image", json={"prompt": "a cat"}
    )
    assert resp.status_code in (401, 403), resp.text


# 12, 13 — unpublished / paused agent rejected --------------------------------


def test_image_generation_unpublished_agent_rejected(client):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _ENABLED_CFG)
    pub = _publish(client, headers, agent["id"])

    unpub = client.post(f"/v2/agents/{agent['id']}/unpublish", headers=headers)
    assert unpub.status_code == 200, unpub.text

    # The api_key from before un-publishing still exists but the agent is no
    # longer PUBLISHED — the same key/agent pair must now be rejected.
    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a cat"}
        )
    assert resp.status_code == 403, resp.text
    assert provider.generate.call_count == 0


def test_image_generation_paused_agent_rejected(client, db_session):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _ENABLED_CFG)
    pub = _publish(client, headers, agent["id"])

    from app.agent_platform.models.agent import AgentConfig

    row = db_session.query(AgentConfig).filter(AgentConfig.id == agent["id"]).first()
    row.status = "PAUSED"
    db_session.commit()

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a cat"}
        )
    assert resp.status_code == 403, resp.text
    assert provider.generate.call_count == 0


# 14 — usage recording ---------------------------------------------------------


def test_image_generation_records_usage(client, db_session):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _ENABLED_CFG)
    pub = _publish(client, headers, agent["id"])

    provider = _mock_provider()
    with _patch_registry(provider):
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a cat"}
        )
    assert resp.status_code == 200, resp.text

    from app.usage.models import UsageEvent

    events = (
        db_session.query(UsageEvent)
        .filter(UsageEvent.dimension == "images_generated")
        .order_by(UsageEvent.created_at.desc())
        .all()
    )
    assert any(e.quantity == 1 for e in events)


# 16 — provider failure ---------------------------------------------------------


def test_image_generation_provider_failure_returns_502(client):
    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _ENABLED_CFG)
    pub = _publish(client, headers, agent["id"])

    provider = _mock_provider(side_effect=RuntimeError("provider exploded"))
    with _patch_registry(provider):
        resp = client.post(
            "/public/v1/image", json={"api_key": pub["api_key"], "prompt": "a cat"}
        )
    assert resp.status_code == 502, resp.text
    assert "provider exploded" not in resp.text  # never leak the raw exception


# 18 — existing text chat regression (spot check, full coverage lives in
# test_agent_management.py / test_publish.py) --------------------------------


def test_existing_text_chat_unaffected_by_image_capability(client):
    from unittest.mock import AsyncMock as _AsyncMock

    from app.agent_platform.schemas import UnifiedChatResponse

    headers, _ = _auth(client)
    agent = _create_agent(client, headers, _ENABLED_CFG)
    pub = _publish(client, headers, agent["id"])

    fake_chat = UnifiedChatResponse(
        content="hi there", provider="openai", model="gpt-4o-mini",
        input_tokens=5, output_tokens=3, total_tokens=8,
    )
    mock_call = _AsyncMock(return_value=fake_chat)
    with patch("app.agent_platform.gateway.service.AIGatewayService.process_request", new=mock_call):
        resp = client.post("/public/v1/chat", json={"api_key": pub["api_key"], "message": "hello"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["reply"] == "hi there"
