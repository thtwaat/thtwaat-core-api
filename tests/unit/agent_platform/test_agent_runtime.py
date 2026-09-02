"""Unit tests for production agent runtime helpers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.agent_platform.agent_runtime import (
    AgentRuntime,
    agent_capabilities,
    build_gateway_messages,
    build_rag_system_prompt,
    detect_handoff_intent,
    extract_lead,
    handoff_wait_message,
    language_system_instruction,
    memory_message_window,
    merge_lead_into_metadata,
    provider_model_supports_vision,
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
    assert caps["vision"] is False


@pytest.mark.unit
def test_capabilities_vision_opt_in():
    caps = agent_capabilities({"capabilities": {"vision": True}})
    assert caps["vision"] is True
    # Existing agents with no capabilities key at all stay fully unaffected.
    assert agent_capabilities({})["vision"] is False
    assert agent_capabilities(None)["vision"] is False


@pytest.mark.unit
def test_capabilities_new_optional_flags_default_false():
    """voice/calling/image_generation must default off for agents with no
    capabilities configured at all — same guarantee as vision above."""
    caps = agent_capabilities({})
    assert caps["voice"] is False
    assert caps["calling"] is False
    assert caps["image_generation"] is False

    caps = agent_capabilities({"capabilities": {"voice": True, "calling": True, "image_generation": True}})
    assert caps["voice"] is True
    assert caps["calling"] is True
    assert caps["image_generation"] is True


@pytest.mark.unit
def test_capabilities_knowledge_key_and_legacy_rag_alias():
    # No capabilities configured at all -> defaults to enabled.
    assert agent_capabilities({})["knowledge"] is True
    assert agent_capabilities(None)["knowledge"] is True

    # New canonical key.
    assert agent_capabilities({"capabilities": {"knowledge": False}})["knowledge"] is False

    # Legacy key written by the existing agent-builder UI ("rag") is honored
    # as a fallback when "knowledge" itself isn't present.
    assert agent_capabilities({"capabilities": {"rag": False}})["knowledge"] is False
    assert agent_capabilities({"capabilities": {"rag": True}})["knowledge"] is True

    # "knowledge" wins if both are present.
    assert agent_capabilities({"capabilities": {"knowledge": True, "rag": False}})["knowledge"] is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "provider,model,expected",
    [
        ("openai", "gpt-4o", True),
        ("openai", "gpt-4o-mini", True),
        ("openai", "GPT-4O-MINI", True),
        ("openai", "gpt-3.5-turbo", False),
        ("anthropic", "claude-3-5-sonnet", False),
        ("gemini", "gemini-1.5-pro", False),
        ("openai", "", False),
        ("", "gpt-4o", False),
    ],
)
def test_provider_model_supports_vision(provider, model, expected):
    assert provider_model_supports_vision(provider, model) is expected


@pytest.mark.unit
def test_check_vision_request_noop_without_image():
    agent = SimpleNamespace(provider="anthropic", model="claude-3-5-sonnet", web_config={})
    caps = {"vision": False}
    AgentRuntime.check_vision_request(agent, caps, has_image=False)  # must not raise


@pytest.mark.unit
def test_check_vision_request_raises_when_capability_disabled():
    agent = SimpleNamespace(provider="openai", model="gpt-4o-mini", web_config={})
    caps = {"vision": False}
    with pytest.raises(HTTPException) as exc_info:
        AgentRuntime.check_vision_request(agent, caps, has_image=True)
    assert exc_info.value.status_code == 400
    assert "vision capability" in exc_info.value.detail


@pytest.mark.unit
def test_check_vision_request_raises_when_provider_unsupported():
    agent = SimpleNamespace(provider="anthropic", model="claude-3-5-sonnet", web_config={})
    caps = {"vision": True}
    with pytest.raises(HTTPException) as exc_info:
        AgentRuntime.check_vision_request(agent, caps, has_image=True)
    assert exc_info.value.status_code == 400
    assert "does not support image input" in exc_info.value.detail


@pytest.mark.unit
def test_check_vision_request_passes_for_openai_gpt4o_with_capability_enabled():
    agent = SimpleNamespace(provider="openai", model="gpt-4o-mini", web_config={})
    caps = {"vision": True}
    AgentRuntime.check_vision_request(agent, caps, has_image=True)  # must not raise


@pytest.mark.unit
def test_build_rag_system_prompt_no_sources():
    agent = SimpleNamespace(system_prompt_template="Be helpful.")
    prompt = build_rag_system_prompt(agent, locale=None, sources=[], caps={"multilingual": False})
    assert prompt == "Be helpful."


@pytest.mark.unit
def test_build_rag_system_prompt_with_sources():
    agent = SimpleNamespace(system_prompt_template="Be helpful.")
    sources = [SimpleNamespace(document_name="doc1", text="fact one")]
    prompt = build_rag_system_prompt(agent, locale=None, sources=sources, caps={"multilingual": False})
    assert "fact one" in prompt
    assert "[1] (Source: doc1)" in prompt
    assert "Original Instructions: Be helpful." in prompt


@pytest.mark.unit
def test_build_gateway_messages_matches_prior_shape():
    msgs = [
        SimpleNamespace(role="user", content="hi"),
        SimpleNamespace(role="human", content="hello from ops"),
    ]
    messages = build_gateway_messages("SYS", msgs, memory_enabled=True)
    assert messages[0] == {"role": "system", "content": "SYS"}
    assert messages[1] == {"role": "user", "content": "hi"}
    assert messages[2] == {"role": "assistant", "content": "hello from ops"}
