"""Tests for AI Calling (telephony): webhook signature enforcement, call
routing/company isolation, capability gating, conversation-as-call-session
persistence, and call-duration usage recording.

Twilio's real HMAC signature isn't computable without a live auth token, so
every test patches ``verify_twilio_signature`` directly — the same function
``TwilioProvider.verify_webhook`` calls — rather than trying to forge a real
signature. A dedicated test asserts the *reject-on-invalid* path using the
real (unpatched) verifier to prove a wrong/missing signature is rejected.
"""
from __future__ import annotations

import re
import uuid
from unittest.mock import AsyncMock, patch

from app.agent_platform.schemas import UnifiedChatResponse

_FAKE_CHAT = UnifiedChatResponse(
    content="Sure, I can help with your order.",
    provider="openai",
    model="gpt-4o-mini",
    input_tokens=10,
    output_tokens=8,
    total_tokens=18,
)


def _auth(client, role: str = "company_owner"):
    company_slug = f"call-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": f"Call Co {company_slug}", "slug": company_slug},
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
            "name": "Call Bot",
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


def _sig_patch(valid: bool = True):
    return patch(
        "app.agent_platform.telephony.twilio_provider.verify_twilio_signature",
        return_value=valid,
    )


def _extract_gather_action(twiml: str) -> str:
    m = re.search(r'action="([^"]+)"', twiml)
    assert m, f"no <Gather action=...> found in: {twiml}"
    return m.group(1).replace("&amp;", "&")


def _query_params(url: str) -> dict:
    from urllib.parse import urlparse, parse_qs

    q = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in q.items()}


def _unique_phone_number() -> str:
    """A fresh E.164-looking number per call — the test DB persists across
    runs (no per-test rollback), so a hardcoded literal risks colliding with
    a same-numbered agent left over from an earlier run and silently routing
    to the wrong one."""
    digits = "".join(str(int(c, 16) % 10) for c in uuid.uuid4().hex[:10])
    return f"+1{digits}"


def test_invalid_signature_is_rejected(client):
    """No signature patch here — the real verifier must reject a
    missing/garbage X-Twilio-Signature header."""
    resp = client.post(
        "/public/v1/telephony/twilio/voice",
        data={"To": "+15551234567", "From": "+15559876543", "CallSid": "CA_bad"},
    )
    assert resp.status_code == 200
    assert "<Reject" in resp.text


def test_incoming_call_no_agent_for_number_rejects(client):
    with _sig_patch(True):
        resp = client.post(
            "/public/v1/telephony/twilio/voice",
            data={"To": _unique_phone_number(), "From": "+15559876543", "CallSid": f"CA{uuid.uuid4().hex}"},
        )
    assert resp.status_code == 200
    assert "<Reject" in resp.text


def test_incoming_call_calling_disabled_rejects(client):
    headers, _ = _auth(client)
    phone = _unique_phone_number()
    _agent, _pub = _create_and_publish_agent(
        client,
        headers,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "calling": {"phone_number": phone},
        },
    )
    with _sig_patch(True):
        resp = client.post(
            "/public/v1/telephony/twilio/voice",
            data={"To": phone, "From": "+15559876543", "CallSid": f"CA{uuid.uuid4().hex}"},
        )
    assert resp.status_code == 200
    assert "<Reject" in resp.text


def test_incoming_call_creates_call_session_and_greets(client):
    headers, _ = _auth(client)
    phone = _unique_phone_number()
    agent, _pub = _create_and_publish_agent(
        client,
        headers,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "capabilities": {"calling": True},
            "calling": {"phone_number": phone, "greeting": "Welcome to Call Bot!"},
        },
    )
    call_sid = f"CA{uuid.uuid4().hex}"
    with _sig_patch(True):
        resp = client.post(
            "/public/v1/telephony/twilio/voice",
            data={"To": phone, "From": "+15559876543", "CallSid": call_sid},
        )
    assert resp.status_code == 200
    assert "<Gather" in resp.text
    assert "Welcome to Call Bot!" in resp.text

    action_url = _extract_gather_action(resp.text)
    params = _query_params(action_url)
    assert params["agent_id"] == agent["id"]
    conversation_id = params["conversation_id"]

    conv_resp = client.get(f"/v2/conversations/{conversation_id}", headers=headers)
    assert conv_resp.status_code == 200, conv_resp.text
    conv = conv_resp.json()
    assert conv["channel"] == "call"


def test_gather_turn_calls_agent_runtime_and_continues_gathering(client):
    headers, _ = _auth(client)
    phone = _unique_phone_number()
    agent, _pub = _create_and_publish_agent(
        client,
        headers,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "capabilities": {"calling": True},
            "calling": {"phone_number": phone},
        },
    )
    call_sid = f"CA{uuid.uuid4().hex}"
    with _sig_patch(True):
        voice_resp = client.post(
            "/public/v1/telephony/twilio/voice",
            data={"To": phone, "From": "+15559876543", "CallSid": call_sid},
        )
    params = _query_params(_extract_gather_action(voice_resp.text))

    gw_mock = AsyncMock(return_value=_FAKE_CHAT)
    with _sig_patch(True), patch(
        "app.agent_platform.gateway.service.AIGatewayService.process_request", new=gw_mock
    ):
        gather_resp = client.post(
            f"/public/v1/telephony/twilio/gather?agent_id={params['agent_id']}&conversation_id={params['conversation_id']}",
            data={"CallSid": call_sid, "SpeechResult": "I need help with my order", "Confidence": "0.9"},
        )
    assert gather_resp.status_code == 200, gather_resp.text
    assert "Sure, I can help with your order." in gather_resp.text
    assert "<Gather" in gather_resp.text  # loop continues
    gw_mock.assert_awaited_once()

    conv_resp = client.get(f"/v2/conversations/{params['conversation_id']}", headers=headers)
    roles_and_content = [(m["role"], m["content"]) for m in conv_resp.json()["messages"]]
    assert ("user", "I need help with my order") in roles_and_content
    assert ("assistant", "Sure, I can help with your order.") in roles_and_content


def test_gather_call_sid_mismatch_is_rejected(client):
    """A gather callback whose CallSid doesn't match the one recorded at
    call start must be rejected — defense in depth beyond signature
    verification (see CallRuntime._resolve_call_session)."""
    headers, _ = _auth(client)
    phone = _unique_phone_number()
    agent, _pub = _create_and_publish_agent(
        client,
        headers,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "capabilities": {"calling": True},
            "calling": {"phone_number": phone},
        },
    )
    call_sid = f"CA{uuid.uuid4().hex}"
    with _sig_patch(True):
        voice_resp = client.post(
            "/public/v1/telephony/twilio/voice",
            data={"To": phone, "From": "+15559876543", "CallSid": call_sid},
        )
    params = _query_params(_extract_gather_action(voice_resp.text))

    with _sig_patch(True):
        gather_resp = client.post(
            f"/public/v1/telephony/twilio/gather?agent_id={params['agent_id']}&conversation_id={params['conversation_id']}",
            data={"CallSid": "CA_totally_different", "SpeechResult": "hi"},
        )
    assert "<Reject" in gather_resp.text


def test_call_cross_company_agent_id_conversation_mismatch_rejected(client):
    """conversation_id from company A's call can't be replayed against
    company B's agent_id."""
    headers_a, _ = _auth(client)
    headers_b, _ = _auth(client)
    phone_a = _unique_phone_number()
    phone_b = _unique_phone_number()
    _agent_a, _pub_a = _create_and_publish_agent(
        client,
        headers_a,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "capabilities": {"calling": True},
            "calling": {"phone_number": phone_a},
        },
    )
    agent_b, _pub_b = _create_and_publish_agent(
        client,
        headers_b,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "capabilities": {"calling": True},
            "calling": {"phone_number": phone_b},
        },
    )
    call_sid = f"CA{uuid.uuid4().hex}"
    with _sig_patch(True):
        voice_resp = client.post(
            "/public/v1/telephony/twilio/voice",
            data={"To": phone_a, "From": "+15559876543", "CallSid": call_sid},
        )
    params = _query_params(_extract_gather_action(voice_resp.text))

    with _sig_patch(True):
        gather_resp = client.post(
            f"/public/v1/telephony/twilio/gather?agent_id={agent_b['id']}&conversation_id={params['conversation_id']}",
            data={"CallSid": call_sid, "SpeechResult": "hi"},
        )
    assert "<Reject" in gather_resp.text


def test_status_callback_closes_conversation_and_records_minutes(client, db_session):
    headers, _ = _auth(client)
    phone = _unique_phone_number()
    _agent, _pub = _create_and_publish_agent(
        client,
        headers,
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "capabilities": {"calling": True},
            "calling": {"phone_number": phone},
        },
    )
    call_sid = f"CA{uuid.uuid4().hex}"
    with _sig_patch(True):
        voice_resp = client.post(
            "/public/v1/telephony/twilio/voice",
            data={"To": phone, "From": "+15559876543", "CallSid": call_sid},
        )
    params = _query_params(_extract_gather_action(voice_resp.text))

    with _sig_patch(True):
        status_resp = client.post(
            "/public/v1/telephony/twilio/status",
            data={"CallSid": call_sid, "CallStatus": "completed", "CallDuration": "125"},
        )
    assert status_resp.status_code == 204

    conv_resp = client.get(f"/v2/conversations/{params['conversation_id']}", headers=headers)
    assert conv_resp.json()["status"] == "closed"

    from app.usage.models import UsageEvent

    events = (
        db_session.query(UsageEvent)
        .filter(UsageEvent.dimension == "call_minutes")
        .order_by(UsageEvent.created_at.desc())
        .all()
    )
    assert any(e.quantity == 3 for e in events)  # ceil(125s / 60) == 3
