"""OpenAI-compatible SSE helpers for chat.completion.chunk (Week 3 Day 3–4)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from app.openai_compat.schemas import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatMessage,
    CompletionUsage,
)
from app.openai_compat.stub import stub_complete


@dataclass
class StreamMaterial:
    """Fully prepared stream payload — safe to idempotency-store before SSE starts."""

    completion_id: str
    model: str
    content: str
    pieces: List[str]
    prompt_tokens: int
    completion_tokens: int
    provider: str
    finish_reason: str
    response: Dict[str, Any]


def format_sse(data: dict | str) -> str:
    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data, separators=(",", ":"), default=str)
    return f"data: {payload}\n\n"


def chunk_payload(
    *,
    completion_id: str,
    created: int,
    model: str,
    delta: ChatCompletionChunkDelta,
    finish_reason: Optional[str] = None,
    usage: Optional[CompletionUsage] = None,
    system_fingerprint: Optional[str] = None,
) -> dict:
    chunk = ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=delta,
                finish_reason=finish_reason,
            )
        ],
        system_fingerprint=system_fingerprint,
        usage=usage,
    )
    return chunk.model_dump(exclude_none=True)


def iter_text_pieces(text: str, *, max_chars: int = 12) -> Iterator[str]:
    """Split assistant text into small pieces for stub/gateway fake-streaming."""
    if not text:
        yield ""
        return
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= max_chars or ch.isspace():
            yield buf
            buf = ""
    if buf:
        yield buf


def stub_stream_pieces(messages: List[ChatMessage], *, model: str) -> tuple[str, int, int, List[str]]:
    content, prompt_tokens, completion_tokens = stub_complete(messages, model=model)
    pieces = list(iter_text_pieces(content))
    return content, prompt_tokens, completion_tokens, pieces


def material_from_stored_response(response: Dict[str, Any]) -> StreamMaterial:
    """Rebuild StreamMaterial from an idempotent stored chat.completion JSON."""
    choices = response.get("choices") or []
    content = ""
    finish_reason = "stop"
    if choices:
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content") or ""
        finish_reason = choices[0].get("finish_reason") or "stop"
    usage = response.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    provider = "replay"
    fp = response.get("system_fingerprint") or ""
    if isinstance(fp, str) and fp.startswith("thtwaat-"):
        provider = fp.replace("thtwaat-", "", 1) or "replay"
    return StreamMaterial(
        completion_id=str(response.get("id") or "chatcmpl_replay"),
        model=str(response.get("model") or "unknown"),
        content=content,
        pieces=list(iter_text_pieces(content)),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=provider,
        finish_reason=finish_reason,
        response=response,
    )


async def aiter_sse_completion(
    *,
    completion_id: str,
    model: str,
    pieces: List[str],
    prompt_tokens: int,
    completion_tokens: int,
    provider: str = "stub",
    include_usage: bool = True,
) -> AsyncIterator[str]:
    """Yield SSE frames for a finished text broken into pieces."""
    created = int(time.time())
    fingerprint = f"thtwaat-{provider}"

    yield format_sse(
        chunk_payload(
            completion_id=completion_id,
            created=created,
            model=model,
            delta=ChatCompletionChunkDelta(role="assistant", content=""),
            system_fingerprint=fingerprint,
        )
    )

    for piece in pieces:
        if not piece:
            continue
        yield format_sse(
            chunk_payload(
                completion_id=completion_id,
                created=created,
                model=model,
                delta=ChatCompletionChunkDelta(content=piece),
                system_fingerprint=fingerprint,
            )
        )

    final_usage = None
    if include_usage:
        final_usage = CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    yield format_sse(
        chunk_payload(
            completion_id=completion_id,
            created=created,
            model=model,
            delta=ChatCompletionChunkDelta(),
            finish_reason="stop",
            usage=final_usage,
            system_fingerprint=fingerprint,
        )
    )
    yield format_sse("[DONE]")


async def aiter_sse_from_material(material: StreamMaterial) -> AsyncIterator[str]:
    async for frame in aiter_sse_completion(
        completion_id=material.completion_id,
        model=material.model,
        pieces=material.pieces,
        prompt_tokens=material.prompt_tokens,
        completion_tokens=material.completion_tokens,
        provider=material.provider,
    ):
        yield frame
