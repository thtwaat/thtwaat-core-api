"""Unit + integration coverage for AI Copilot."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.copilot.intents import (
    DESTRUCTIVE_TOOLS,
    TOOL_CATALOG,
    WORKFLOWS,
    CopilotIntent,
    TaskStatus,
)
from app.copilot.nlu import detect_intent, extract_slots, missing_required_slots
from app.copilot.schemas import ChatRequest, ConfirmTaskRequest
from app.copilot.service import CopilotService
from app.copilot.tools import CopilotToolRuntime, _slugify


def test_intent_detection_examples():
    intent, conf, hits = detect_intent("Create a customer support chatbot.")
    assert intent == CopilotIntent.GENERATE_PRODUCT
    assert conf >= 0.45

    intent, _, _ = detect_intent("Publish my AI product")
    assert intent == CopilotIntent.PUBLISH_WEBSITE

    intent, _, _ = detect_intent("Connect my domain chat.acme.com")
    assert intent == CopilotIntent.CONNECT_DOMAIN

    intent, _, _ = detect_intent("Show platform health")
    assert intent == CopilotIntent.SHOW_HEALTH

    intent, _, _ = detect_intent("Why did deployment fail?")
    assert intent == CopilotIntent.VIEW_MONITORING


def test_slot_extraction():
    slots = extract_slots(
        "Connect my domain chat.acme.com and invite owner@acme.com",
        CopilotIntent.CONNECT_DOMAIN,
    )
    assert slots.get("hostname") == "chat.acme.com"

    slots = extract_slots(
        "Invite owner@acme.com to the team",
        CopilotIntent.INVITE_MEMBERS,
    )
    assert slots["email"] == "owner@acme.com"
    assert missing_required_slots(CopilotIntent.INVITE_MEMBERS, {}) == ["email"]

    slots = extract_slots(
        "Install template customer-support",
        CopilotIntent.INSTALL_TEMPLATE,
    )
    assert slots.get("template_slug") == "customer-support"


def test_workflows_cover_required_capabilities():
    required = {
        CopilotIntent.CREATE_AGENT,
        CopilotIntent.GENERATE_PRODUCT,
        CopilotIntent.INSTALL_TEMPLATE,
        CopilotIntent.UPLOAD_KNOWLEDGE,
        CopilotIntent.PUBLISH_WEBSITE,
        CopilotIntent.CONFIGURE_BRANDING,
        CopilotIntent.CONNECT_DOMAIN,
        CopilotIntent.CREATE_ORGANIZATION,
        CopilotIntent.INVITE_MEMBERS,
        CopilotIntent.SHOW_REPORTS,
        CopilotIntent.VIEW_MONITORING,
        CopilotIntent.RETRY_FAILED_JOB,
    }
    assert required <= set(WORKFLOWS)
    assert "publish_agent" in DESTRUCTIVE_TOOLS
    assert any(t["name"] == "generate_product" for t in TOOL_CATALOG)


def test_slugify():
    assert _slugify("Acme Corp!") == "acme-corp"


def test_tool_runtime_unknown_tool():
    rt = CopilotToolRuntime(MagicMock(), uuid.uuid4(), uuid.uuid4(), "company_owner")
    with pytest.raises(HTTPException) as exc:
        rt.execute("not_a_real_tool", {})
    assert exc.value.status_code == 400


def test_tool_runtime_platform_admin_gate():
    rt = CopilotToolRuntime(MagicMock(), uuid.uuid4(), uuid.uuid4(), "employee")
    with pytest.raises(HTTPException) as exc:
        rt.show_health({})
    assert exc.value.status_code == 403


def test_create_agent_tool(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    rt = CopilotToolRuntime(db, uuid.uuid4(), uuid.uuid4(), "company_owner")
    rt.usage.check_quota = MagicMock()
    rt.usage.record = MagicMock()

    # capture AgentConfig add
    added = {}

    def add(obj):
        added["agent"] = obj
        obj.id = uuid.uuid4()

    db.add.side_effect = add
    out = rt.create_agent({"agent_name": "Support Bot"})
    assert out["name"] == "Support Bot"
    assert out["status"] == "DRAFT"
    assert "agent_id" in out


def test_chat_help_without_db_heavy_path(monkeypatch):
    db = MagicMock()
    svc = CopilotService(db)

    conversation = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        memory={},
        title=None,
    )
    svc._get_or_create_conversation = MagicMock(return_value=conversation)  # type: ignore
    msg = SimpleNamespace(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content="help",
        intent="help",
        confidence="0.5",
        meta={},
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    svc._add_message = MagicMock(side_effect=[MagicMock(), msg])  # type: ignore
    svc._msg_response = MagicMock(
        return_value=SimpleNamespace(
            id=msg.id,
            conversation_id=conversation.id,
            role="assistant",
            content="I'm the THTWAAT",
            intent="help",
            confidence="0.5",
            metadata={},
            created_at=msg.created_at,
        )
    )  # type: ignore

    # Bypass MessageResponse validation by returning ChatResponse manually path —
    # instead call detect path with HELP via real chat after fixing _msg_response properly.
    from app.copilot.schemas import MessageResponse
    from app.copilot.intents import MessageRole
    from datetime import datetime, timezone

    def msg_resp(m):
        return MessageResponse(
            id=m.id if hasattr(m, "id") else uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=getattr(m, "content", "help text"),
            intent="help",
            confidence="0.9",
            meta={},
            created_at=datetime.now(timezone.utc),
        )

    user_msg = SimpleNamespace(id=uuid.uuid4(), content="help", created_at=datetime.now(timezone.utc))
    asst_msg = SimpleNamespace(
        id=uuid.uuid4(),
        content="I'm the THTWAAT AI Copilot.",
        created_at=datetime.now(timezone.utc),
    )
    svc._add_message = MagicMock(side_effect=[user_msg, asst_msg])  # type: ignore
    svc._msg_response = msg_resp  # type: ignore
    db.commit = MagicMock()

    result = svc.chat(
        conversation.company_id,
        conversation.user_id,
        "company_owner",
        ChatRequest(message="help"),
    )
    assert result.intent == CopilotIntent.HELP
    assert result.task is None


def test_plan_requires_confirmation():
    svc = CopilotService(MagicMock())
    assert svc._plan_requires_confirmation([{"tool": "publish_agent"}]) is True
    assert svc._plan_requires_confirmation([{"tool": "create_agent"}]) is False


@pytest.mark.integration
def test_copilot_tools_endpoint(client):
    resp = client.get("/api/v1/copilot/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["tools"]) >= 10
    assert any(w["intent"] == "generate_product" for w in body["workflows"])
