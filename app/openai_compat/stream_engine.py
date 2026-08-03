"""Production streaming engine — true SSE from provider adapters (Sem03 W2 D1)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from fastapi import Request

from app.openai_compat.errors import map_provider_exception, openai_error
from app.openai_compat.inference_adapter import new_completion_id
from app.openai_compat.providers.stream_factory import get_streaming_adapter, stream_enabled
from app.openai_compat.providers.stream_metrics import (
    StreamRunMetrics,
    get_streaming_metrics,
)
from app.openai_compat.providers.streaming_adapter import (
    StreamingAdapter,
    messages_as_dicts,
)
from app.openai_compat.schemas import (
    ChatCompletionChunkDelta,
    CompletionUsage,
)
from app.openai_compat.streaming import chunk_payload, format_sse

logger = logging.getLogger(__name__)


@dataclass
class StreamEngineResult:
    completion_id: str
    model: str
    provider: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str
    cancelled: bool
    response: Dict[str, Any] = field(default_factory=dict)
    metrics: Optional[StreamRunMetrics] = None


class StreamEngine:
    """
    Routes to a StreamingAdapter, emits OpenAI SSE frames, tracks metrics,
    and cancels upstream on client disconnect.
    """

    def __init__(self, adapter: Optional[StreamingAdapter] = None) -> None:
        self.adapter = adapter
        self.result: Optional[StreamEngineResult] = None
        self._adapter_owned = adapter

    def assert_enabled(self) -> None:
        if not stream_enabled():
            raise openai_error(
                status_code=400,
                message="Streaming is disabled (STREAM_ENABLED=false)",
                type_="invalid_request_error",
                code="stream_disabled",
            )

    async def aiter_sse(
        self,
        *,
        model: str,
        messages: Sequence[Any],
        provider_name: str,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        request: Optional[Request] = None,
        completion_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        self.assert_enabled()
        adapter = self.adapter or get_streaming_adapter(provider_name)
        self._adapter_owned = adapter
        cid = completion_id or new_completion_id()
        created = int(time.time())
        fingerprint = f"thtwaat-{adapter.name}"
        started = time.perf_counter()
        first_token_at: Optional[float] = None
        content_parts: List[str] = []
        streamed_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        finish_reason = "stop"
        cancelled = False
        role_emitted = False
        error_code: Optional[str] = None

        msg_dicts = messages_as_dicts(messages)

        try:
            async for delta in adapter.stream_chat(
                model=model,
                messages=msg_dicts,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                if request is not None and await request.is_disconnected():
                    cancelled = True
                    await adapter.cancel()
                    break

                if delta.role and not role_emitted:
                    role_emitted = True
                    yield format_sse(
                        chunk_payload(
                            completion_id=cid,
                            created=created,
                            model=model,
                            delta=ChatCompletionChunkDelta(
                                role=delta.role, content=delta.content or ""
                            ),
                            system_fingerprint=fingerprint,
                        )
                    )
                    continue

                if delta.content:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    if not role_emitted:
                        role_emitted = True
                        yield format_sse(
                            chunk_payload(
                                completion_id=cid,
                                created=created,
                                model=model,
                                delta=ChatCompletionChunkDelta(role="assistant", content=""),
                                system_fingerprint=fingerprint,
                            )
                        )
                    content_parts.append(delta.content)
                    # Approximate tokens as whitespace-ish chunks
                    streamed_tokens += max(1, len(delta.content.split()))
                    yield format_sse(
                        chunk_payload(
                            completion_id=cid,
                            created=created,
                            model=model,
                            delta=ChatCompletionChunkDelta(content=delta.content),
                            system_fingerprint=fingerprint,
                        )
                    )

                if delta.prompt_tokens is not None:
                    prompt_tokens = int(delta.prompt_tokens)
                if delta.completion_tokens is not None:
                    completion_tokens = int(delta.completion_tokens)
                if delta.finish_reason:
                    finish_reason = delta.finish_reason
                if delta.done:
                    break
        except Exception as exc:
            error_code = type(exc).__name__
            await adapter.cancel()
            mapped = map_provider_exception(exc)
            err_body = mapped.detail if isinstance(mapped.detail, dict) else {}
            err_code = (err_body.get("error") or {}).get("code") or "upstream_error"
            if role_emitted or content_parts:
                yield format_sse(
                    {
                        "error": {
                            "message": str(exc),
                            "type": "api_error",
                            "code": err_code,
                        }
                    }
                )
                yield format_sse("[DONE]")
                duration_ms = (time.perf_counter() - started) * 1000.0
                run = StreamRunMetrics(
                    first_token_latency_ms=(
                        (first_token_at - started) * 1000.0 if first_token_at else None
                    ),
                    total_stream_duration_ms=duration_ms,
                    streamed_tokens=streamed_tokens,
                    cancelled=False,
                    error=error_code,
                    provider=adapter.name,
                )
                get_streaming_metrics().record(run)
                self.result = StreamEngineResult(
                    completion_id=cid,
                    model=model,
                    provider=adapter.name,
                    content="".join(content_parts),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens or streamed_tokens,
                    finish_reason="stop",
                    cancelled=False,
                    metrics=run,
                )
                return
            raise mapped from exc

        content = "".join(content_parts)
        if completion_tokens <= 0:
            completion_tokens = streamed_tokens or (max(1, len(content) // 4) if content else 0)
        if prompt_tokens <= 0:
            prompt_tokens = max(1, sum(len(str(m.get("content") or "")) for m in msg_dicts) // 4)

        if not cancelled:
            usage = CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )
            if not role_emitted:
                # empty stream — still emit role + finish
                yield format_sse(
                    chunk_payload(
                        completion_id=cid,
                        created=created,
                        model=model,
                        delta=ChatCompletionChunkDelta(role="assistant", content=""),
                        system_fingerprint=fingerprint,
                    )
                )
            yield format_sse(
                chunk_payload(
                    completion_id=cid,
                    created=created,
                    model=model,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason=finish_reason,
                    usage=usage,
                    system_fingerprint=fingerprint,
                )
            )
            yield format_sse("[DONE]")

        duration_ms = (time.perf_counter() - started) * 1000.0
        ttft = (first_token_at - started) * 1000.0 if first_token_at else None
        run = StreamRunMetrics(
            first_token_latency_ms=ttft,
            total_stream_duration_ms=duration_ms,
            streamed_tokens=streamed_tokens,
            cancelled=cancelled,
            error=error_code,
            provider=adapter.name,
        )
        get_streaming_metrics().record(run)

        response = {
            "id": cid,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                    "logprobs": None,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "system_fingerprint": fingerprint,
        }
        self.result = StreamEngineResult(
            completion_id=cid,
            model=model,
            provider=adapter.name,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
            cancelled=cancelled,
            response=response,
            metrics=run,
        )


async def resolve_stream_provider_name(
    *,
    model: str,
    provider: Optional[str],
) -> str:
    """Reuse Day 3 router selection (chat capability) without invoking chat()."""
    from app.openai_compat.inference_routing_service import InferenceRoutingService
    from app.openai_compat.providers.capabilities import ProviderCapability

    decision = await InferenceRoutingService().select_provider(
        model=model,
        provider=provider,
        capability=ProviderCapability.CHAT,
    )
    name = decision.provider_name
    # Day 1 stream support: ollama + openai only
    if name not in {"ollama", "openai"}:
        raise openai_error(
            status_code=400,
            message=(
                f"True streaming is not available for provider '{name}' yet "
                f"(Sem03 W2 D1 supports ollama and openai)."
            ),
            type_="invalid_request_error",
            code="stream_provider_unsupported",
            param="provider",
        )
    return name
