"""Week 3 Day 3 — SSE streaming helpers + service stream path."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage
from app.openai_compat.service import CompletionsService
from app.openai_compat.streaming import (
    aiter_sse_completion,
    format_sse,
    iter_text_pieces,
    stub_stream_pieces,
)


@pytest.mark.unit
def test_format_sse_and_done():
    assert format_sse({"a": 1}) == 'data: {"a":1}\n\n'
    assert format_sse("[DONE]") == "data: [DONE]\n\n"


@pytest.mark.unit
def test_iter_text_pieces_splits():
    pieces = list(iter_text_pieces("Hello world from THTWAAT", max_chars=8))
    assert "".join(pieces) == "Hello world from THTWAAT"
    assert len(pieces) >= 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_aiter_sse_ends_with_done():
    frames = []
    async for frame in aiter_sse_completion(
        completion_id="chatcmpl_x",
        model="stub",
        pieces=["Hi", " there"],
        prompt_tokens=1,
        completion_tokens=2,
    ):
        frames.append(frame)
    assert frames[-1] == "data: [DONE]\n\n"
    assert any('"object":"chat.completion.chunk"' in f for f in frames)
    # Parse a middle content chunk
    mid = next(f for f in frames if "there" in f)
    payload = json.loads(mid.removeprefix("data: ").strip())
    assert payload["choices"][0]["delta"]["content"] == " there"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_completion_yields_sse(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    monkeypatch.setattr(
        "app.openai_compat.usage.record_completion_usage",
        lambda *a, **k: {"recorded": False},
    )
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_WEBHOOKS_ENABLED",
        False,
        raising=False,
    )
    db = MagicMock()
    svc = CompletionsService(db)
    svc.repo = MagicMock()
    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="thtwaat-stub-mini",
        messages=[ChatMessage(role="user", content="stream please")],
        stream=True,
    )
    frames = []
    async for frame in svc.stream_completion(principal, body):
        frames.append(frame)
    assert frames[-1].startswith("data: [DONE]")
    assert svc.repo.create.called
    joined = "".join(frames)
    assert "chat.completion.chunk" in joined


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_completion_still_guards_stream_flag(monkeypatch):
    monkeypatch.setattr(
        "app.openai_compat.service.settings.OPENAI_COMPAT_INFERENCE",
        "stub",
        raising=False,
    )
    svc = CompletionsService(MagicMock())
    principal = CompletionsPrincipal(company_id=uuid.uuid4())
    body = ChatCompletionRequest(
        model="m",
        messages=[ChatMessage(role="user", content="hi")],
        stream=True,
    )
    with pytest.raises(HTTPException) as exc:
        await svc.create_completion(principal, body)
    assert exc.value.detail["error"]["code"] == "stream_use_sse_path"


@pytest.mark.unit
def test_stub_stream_pieces_roundtrip():
    content, pt, ct, pieces = stub_stream_pieces(
        [ChatMessage(role="user", content="hi")], model="m"
    )
    assert content
    assert "".join(pieces) == content
    assert pt >= 1 and ct >= 1
