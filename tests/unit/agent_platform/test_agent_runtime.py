"""Unit tests for production agent runtime helpers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent_platform.agent_runtime import (
    agent_capabilities,
    detect_handoff_intent,
    extract_lead,
    handoff_wait_message,
    language_system_instruction,
    memory_message_window,
    merge_lead_into_metadata,
    resolve_locale,
    to_gateway_role,
)


@pytest.mark.unit
def test_detect_handoff_intent():
    assert detect_handoff_intent("Please talk to a human")
    assert detect_handoff_intent("I need a real person")
    assert not detect_handoff_intent("What is your pricing?")


@pytest.mark.unit
def test_extract_and_merge_lead():
    lead = extract_lead({"lead": {"name": "Ada", "email": "ada@example.com"}})
    assert lead["email"] == "ada@example.com"
    merged = merge_lead_into_metadata({"foo": 1}, lead)
    assert merged["lead"]["name"] == "Ada"
    assert merged["email"] == "ada@example.com"


@pytest.mark.unit
def test_locale_and_language_instruction():
    assert resolve_locale(metadata={"locale": "hi-IN"}) == "hi"
    assert "Hindi" in language_system_instruction("hi")
    assert handoff_wait_message("hi")


@pytest.mark.unit
def test_memory_window_and_human_role():
    msgs = [
        SimpleNamespace(role="user", content="a"),
        SimpleNamespace(role="assistant", content="b"),
        SimpleNamespace(role="human", content="c"),
        SimpleNamespace(role="tool", content="d"),
    ]
    window = memory_message_window(msgs, enabled=True, max_messages=3)
    assert len(window) == 3
    assert to_gateway_role("human") == "assistant"
    disabled = memory_message_window(msgs, enabled=False)
    assert len(disabled) <= 2


@pytest.mark.unit
def test_capabilities_defaults():
    caps = agent_capabilities({"capabilities": {"handoff": False}})
    assert caps["handoff"] is False
    assert caps["memory"] is True
