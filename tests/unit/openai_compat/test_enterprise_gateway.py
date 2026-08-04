"""Phase 5 enterprise AI gateway — unit tests."""
from __future__ import annotations

import asyncio

import pytest

from app.openai_compat.policies.retry import RetryPolicy, with_retry
from app.openai_compat.providers import ensure_providers_registered
from app.openai_compat.providers.capabilities import ProviderCapability, has_capability
from app.openai_compat.providers.registry import reset_registry_for_tests
from app.openai_compat.providers.stream_factory import get_streaming_adapter
from app.openai_compat.schemas import ChatCompletionRequest
from app.openai_compat.tools import normalize_tool_choice, normalize_tools
from app.openai_compat.vision import flatten_text, is_vision_content, normalize_message_content
from app.ai.gateway_workspace import KNOWN_PROVIDERS, PROVIDER_CAPABILITIES


@pytest.mark.unit
def test_openrouter_registered_in_compat_registry():
    reset_registry_for_tests()
    reg = ensure_providers_registered()
    assert "openrouter" in reg.registered_names()
    assert set(["openai", "gemini", "anthropic", "ollama", "openrouter"]).issubset(
        set(reg.registered_names())
    )


@pytest.mark.unit
def test_openrouter_streaming_adapter_resolves():
    adapter = get_streaming_adapter("openrouter")
    assert adapter.name == "openrouter"


@pytest.mark.unit
def test_vision_content_helpers():
    parts = [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": {"url": "https://example.com/a.png"}},
    ]
    assert is_vision_content(parts) is True
    assert is_vision_content("plain") is False
    norm = normalize_message_content(parts)
    assert isinstance(norm, list)
    assert flatten_text(parts).startswith("What is")


@pytest.mark.unit
def test_tool_normalization():
    tools = normalize_tools(
        [
            {"name": "get_weather", "description": "Weather", "parameters": {"type": "object"}},
            {
                "type": "function",
                "function": {"name": "search", "parameters": {"type": "object", "properties": {}}},
            },
        ]
    )
    assert len(tools) == 2
    assert tools[0]["type"] == "function"
    assert normalize_tool_choice("auto") == "auto"


@pytest.mark.unit
def test_chat_completion_request_accepts_tools_and_vision():
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe"},
                    {"type": "image_url", "image_url": {"url": "https://x/y.png"}},
                ],
            }
        ],
        tools=[{"type": "function", "function": {"name": "lookup", "parameters": {}}}],
        tool_choice="auto",
        provider="openrouter",
        rag_query="pricing FAQ",
    )
    assert req.provider == "openrouter"
    assert req.tools and req.tools[0]["function"]["name"] == "lookup"


@pytest.mark.unit
def test_capability_detection_includes_vision_tools():
    assert has_capability(["chat", "vision"], ProviderCapability.VISION)
    assert "vision" in PROVIDER_CAPABILITIES["openai"]
    assert "openrouter" in KNOWN_PROVIDERS


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_policy_succeeds_after_failure():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    result = await with_retry(flaky, policy=RetryPolicy(max_attempts=3, backoff_ms=1, timeout_seconds=5))
    assert result == "ok"
    assert calls["n"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gateway_load_smoke_concurrent_retries():
    """Lightweight load smoke: many concurrent retrying calls."""

    async def one(i: int) -> int:
        async def work():
            await asyncio.sleep(0.001)
            return i

        return await with_retry(work, policy=RetryPolicy(max_attempts=1, backoff_ms=0, timeout_seconds=2))

    results = await asyncio.gather(*[one(i) for i in range(50)])
    assert results == list(range(50))
