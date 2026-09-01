"""Tests for the voice capability: capability gate, STT->AgentRuntime->TTS
wiring, conversation persistence, and company isolation.

The global HTTPException handler (app/api/exceptions.py) reshapes error
bodies to ``{"error": ..., "code": ...}`` (not FastAPI's default
``{"detail": ...}``) — assertions below match that actual shape.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from app.agent_platform.schemas import UnifiedChatResponse
from app.agent_platform.voice.schemas import STTResult, TTSResult

_FAKE_CHAT = UnifiedChatResponse(
    content="I can help with that.",
    provider="openai",
    model="gpt-4o-mini",
    input_tokens=12,
    output_tokens=6,
    total_tokens=18,
)


def _auth(client, role: str = "company_owner"):
    company_slug = f"voice-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Voice Co {company_slug}", "slug": company_slug},
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


def _create_and_publish_agent(client, headers, web_config, name: str = "Voice Bot"):
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
    agent = resp.json()
    pub = client.post(f"/api/v1/agents/{agent['id']}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return agent, pub.json()


def _mock_stt(text: str = "hello there"):
    return AsyncMock(
        return_value=STTResult(text=text, language="en", duration_seconds=2.0, provider="openai", model="whisper-1")
    )


def _mock_tts(audio: bytes = b"FAKE_MP3_BYTES"):
    return AsyncMock(
        return_value=TTSResult(audio_bytes=audio, mime_type="audio/mpeg", duration_seconds=1.5, provider="openai", model="tts-1")
    )


def _patched_voice(stt_transcribe=None, tts_synthesize=None, gateway_response=None):
    """Context-manager-friendly bundle of the three patches every voice test needs."""
    stt_provider = AsyncMock()
    stt_provider.transcribe = stt_transcribe or _mock_stt()
    tts_provider = AsyncMock()
    tts_provider.synthesize = tts_synthesize or _mock_tts()

    return (
        patch(
            "app.agent_platform.voice.voice_runtime.STTProviderRegistry.get_provider",
            return_value=stt_provider,
        ),
        patch(
            "app.agent_platform.voice.voice_runtime.TTSProviderRegistry.get_provider",
            return_value=tts_provider,
        ),
        patch(
            "app.agent_platform.gateway.service.AIGatewayService.process_request",
            new=AsyncMock(return_value=gateway_response or _FAKE_CHAT),
        ),
        stt_provider,
        tts_provider,
    )


_AUDIO_FILE = {"audio": ("clip.wav", b"not-real-audio-bytes", "audio/wav")}


def test_voice_disabled_agent_rejects_audio(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(client, headers, {"provider": "openai", "model": "gpt-4o-mini"})

    p1, p2, p3, stt, _tts = _patched_voice()
    with p1, p2, p3:
        resp = client.post(
            "/public/v1/voice",
            files=_AUDIO_FILE,
            data={"api_key": pub["api_key"]},
        )
    assert resp.status_code == 400, resp.text
    assert "voice capability" in resp.json()["error"]
    assert stt.transcribe.call_count == 0


def test_voice_dashboard_endpoint_same_gate(client):
    headers, _ = _auth(client)
    agent, _pub = _create_and_publish_agent(client, headers, {"provider": "openai", "model": "gpt-4o-mini"})

    p1, p2, p3, stt, _tts = _patched_voice()
    with p1, p2, p3:
        resp = client.post(
            f"/v2/agents/{agent['id']}/voice",
            files=_AUDIO_FILE,
            headers=headers,
        )
    assert resp.status_code == 400, resp.text
    assert stt.transcribe.call_count == 0


def test_voice_enabled_public_roundtrip(client):
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(
        client,
        headers,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"voice": True}},
    )

    p1, p2, p3, stt, tts = _patched_voice()
    with p1, p2, p3:
        resp = client.post(
            "/public/v1/voice",
            files=_AUDIO_FILE,
            data={"api_key": pub["api_key"]},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["transcript"] == "hello there"
    assert body["reply"] == "I can help with that."
    assert body["audio_mime_type"] == "audio/mpeg"

    import base64

    assert base64.b64decode(body["audio_base64"]) == b"FAKE_MP3_BYTES"

    # STT ran before the LLM call, and the transcript (not raw audio) is what
    # reached AgentRuntime/the gateway.
    stt.transcribe.assert_awaited_once()
    tts.synthesize.assert_awaited_once()
    # The LLM's reply text (not the transcript) is what gets synthesized back.
    assert tts.synthesize.await_args.args[0] == "I can help with that."


def test_voice_dashboard_enabled_roundtrip_and_conversation_persists(client):
    headers, _ = _auth(client)
    agent, _pub = _create_and_publish_agent(
        client,
        headers,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"voice": True}},
    )

    p1, p2, p3, stt, tts = _patched_voice()
    with p1, p2, p3:
        resp = client.post(
            f"/v2/agents/{agent['id']}/voice",
            files=_AUDIO_FILE,
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    conversation_id = body["conversation_id"]

    conv_resp = client.get(f"/v2/conversations/{conversation_id}", headers=headers)
    assert conv_resp.status_code == 200, conv_resp.text
    conv = conv_resp.json()
    assert conv["channel"] == "voice"
    roles_and_content = [(m["role"], m["content"]) for m in conv["messages"]]
    assert ("user", "hello there") in roles_and_content
    assert ("assistant", "I can help with that.") in roles_and_content


def test_voice_cross_company_isolation_still_holds(client):
    headers_a, _ = _auth(client)
    headers_b, _ = _auth(client)
    # Distinct names -> distinct slugs, so the by-slug lookup below can't
    # silently resolve to company B's OWN same-slug agent instead of a real
    # cross-tenant hit (slugs are unique per-company, not globally).
    agent_a, pub_a = _create_and_publish_agent(
        client,
        headers_a,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"voice": True}},
        name="Voice Bot Company A",
    )
    _, pub_b = _create_and_publish_agent(
        client,
        headers_b,
        {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"voice": True}},
        name="Voice Bot Company B",
    )

    p1, p2, p3, _stt, _tts = _patched_voice()
    with p1, p2, p3:
        resp = client.post(
            f"/public/v1/agents/{agent_a['slug']}/voice",
            files=_AUDIO_FILE,
            data={"api_key": pub_b["api_key"]},
        )
    assert resp.status_code in (403, 404), resp.text


def test_voice_empty_transcript_skips_ai_call(client):
    """An unintelligible/silent clip shouldn't burn an LLM call — VoiceRuntime
    short-circuits to a re-prompt before ever calling AgentRuntime."""
    headers, _ = _auth(client)
    agent, pub = _create_and_publish_agent(
        client, headers, {"provider": "openai", "model": "gpt-4o-mini", "capabilities": {"voice": True}}
    )

    p1, p2, p3, stt, tts = _patched_voice(stt_transcribe=_mock_stt(text="   "))
    with p1, p2, p3 as gw_mock:
        resp = client.post(
            "/public/v1/voice",
            files=_AUDIO_FILE,
            data={"api_key": pub["api_key"]},
        )
    assert resp.status_code == 200, resp.text
    assert "didn't catch" in resp.json()["reply"]
    assert gw_mock.call_count == 0
    tts.synthesize.assert_awaited_once()
