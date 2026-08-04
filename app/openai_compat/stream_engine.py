"""Production streaming engine — reliability + health (Sem03 W2 D2–D3).

Features:
- provider routing (auto|ollama|openai|gemini|anthropic)
- health-aware skip + TTL cooldown (health cache)
- fallback before first token only
- connect / first-token / idle timeouts
- backpressure (max queued SSE frames)
- metrics + structured per-request logs
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Union

from fastapi import Request

from app.config.settings import settings
from app.openai_compat.errors import map_provider_exception, openai_error
from app.openai_compat.inference_adapter import new_completion_id
from app.openai_compat.providers.base import (
    ProviderTimeoutError,
    ProviderUpstreamError,
)
from app.openai_compat.providers.health_cache import get_health_cache
from app.openai_compat.providers.stream_factory import get_streaming_adapter, stream_enabled
from app.openai_compat.providers.stream_metrics import (
    StreamRunMetrics,
    get_streaming_metrics,
)
from app.openai_compat.providers.streaming_adapter import (
    StreamingAdapter,
    StreamDelta,
    messages_as_dicts,
)
from app.openai_compat.schemas import ChatCompletionChunkDelta, CompletionUsage
from app.openai_compat.streaming import chunk_payload, format_sse

logger = logging.getLogger(__name__)


def _mark_provider_unhealthy(provider: str, cause: BaseException) -> None:
    """Circuit-breaker style cooldown via shared health cache TTL."""
    ttl = float(getattr(settings, "INFERENCE_HEALTH_CACHE_TTL_SECONDS", 30) or 30)
    cache = get_health_cache()
    cache.set_ttl(ttl)
    cache.put(
        provider,
        {"ok": False, "error": str(cause), "source": "stream_pre_token"},
    )
    get_streaming_metrics().mark_provider_unhealthy(provider)


def _mark_provider_healthy(provider: str) -> None:
    ttl = float(getattr(settings, "INFERENCE_HEALTH_CACHE_TTL_SECONDS", 30) or 30)
    cache = get_health_cache()
    cache.set_ttl(ttl)
    cache.put(provider, {"ok": True, "source": "stream_success"})


class StreamPreTokenError(Exception):
    """Provider failed before any token was emitted — eligible for fallback."""

    def __init__(self, provider: str, cause: BaseException) -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(f"{provider}: {cause}")


class StreamSlowClientError(Exception):
    """Client consumed SSE too slowly — queue backpressure tripped."""


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
    fallback_used: bool = False
    providers_tried: List[str] = field(default_factory=list)


def _setting_float(name: str, default: float) -> float:
    raw = getattr(settings, name, default)
    try:
        return max(0.1, float(raw))
    except (TypeError, ValueError):
        return default


def _setting_int(name: str, default: int) -> int:
    raw = getattr(settings, name, default)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return default


class StreamEngine:
    """
    Routes to StreamingAdapter(s), emits OpenAI SSE, applies Day-2 reliability,
    and cancels upstream on client disconnect / slow-client backpressure.
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
        provider_name: str | None = None,
        provider_chain: Optional[Union[Sequence[str], Any]] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        request: Optional[Request] = None,
        completion_id: Optional[str] = None,
        request_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        self.assert_enabled()
        metrics = get_streaming_metrics()
        metrics.mark_started()

        cid = completion_id or new_completion_id()
        req_id = request_id or cid
        created = int(time.time())
        started = time.perf_counter()
        msg_dicts = messages_as_dicts(messages)

        chain: List[str]
        if self.adapter is not None and provider_chain is None:
            # Unit tests inject a scripted adapter — never fan out to real providers.
            try:
                async for frame in self._run_provider_stream(
                    adapter=self.adapter,
                    model=model,
                    messages=msg_dicts,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request=request,
                    completion_id=cid,
                    created=created,
                    started=started,
                    request_id=req_id,
                    tenant_id=tenant_id,
                    fallback_used=False,
                    providers_tried=[getattr(self.adapter, "name", "injected")],
                ):
                    yield frame
                return
            except StreamPreTokenError as exc:
                duration_ms = (time.perf_counter() - started) * 1000.0
                run = StreamRunMetrics(
                    total_stream_duration_ms=duration_ms,
                    error=type(exc.cause).__name__,
                    provider=getattr(self.adapter, "name", "injected"),
                    request_id=req_id,
                    tenant_id=str(tenant_id) if tenant_id is not None else None,
                    outcome="failed",
                )
                metrics.record(run)
                raise map_provider_exception(exc.cause) from exc.cause

        if provider_chain:
            from app.openai_compat.stream_routing import StreamProviderChain

            if isinstance(provider_chain, StreamProviderChain):
                skipped_unhealthy = list(provider_chain.skipped_unhealthy)
                chain = list(provider_chain.providers)
            else:
                skipped_unhealthy = []
                chain = [p.strip().lower() for p in provider_chain if p and str(p).strip()]
        elif provider_name:
            from app.openai_compat.stream_routing import resolve_stream_provider_chain

            resolved = await resolve_stream_provider_chain(
                model=model, provider=provider_name
            )
            chain = list(resolved.providers)
            skipped_unhealthy = list(resolved.skipped_unhealthy)
        else:
            from app.openai_compat.stream_routing import resolve_stream_provider_chain

            resolved = await resolve_stream_provider_chain(model=model, provider="auto")
            chain = list(resolved.providers)
            skipped_unhealthy = list(resolved.skipped_unhealthy)

        if skipped_unhealthy:
            metrics.record_health_skipped(len(skipped_unhealthy))
            logger.info(
                "openai_compat.stream_health_skip request_id=%s skipped=%s",
                req_id,
                ",".join(skipped_unhealthy),
            )

        if not chain:
            chain = ["ollama"]

        last_exc: Optional[BaseException] = None
        providers_tried: List[str] = []
        fallback_used = False

        for index, pname in enumerate(chain):
            providers_tried.append(pname)
            if index > 0:
                fallback_used = True
            adapter = get_streaming_adapter(pname)
            self._adapter_owned = adapter
            try:
                async for frame in self._run_provider_stream(
                    adapter=adapter,
                    model=model,
                    messages=msg_dicts,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request=request,
                    completion_id=cid,
                    created=created,
                    started=started,
                    request_id=req_id,
                    tenant_id=tenant_id,
                    fallback_used=fallback_used,
                    providers_tried=providers_tried,
                    health_skipped=len(skipped_unhealthy),
                    skipped_unhealthy=skipped_unhealthy,
                ):
                    yield frame
                return
            except StreamPreTokenError as exc:
                last_exc = exc.cause
                _mark_provider_unhealthy(pname, exc.cause)
                logger.warning(
                    "openai_compat.stream_fallback provider=%s request_id=%s err=%s",
                    pname,
                    req_id,
                    exc.cause,
                )
                continue

        # All providers failed before first token
        duration_ms = (time.perf_counter() - started) * 1000.0
        run = StreamRunMetrics(
            total_stream_duration_ms=duration_ms,
            error=type(last_exc).__name__ if last_exc else "no_provider",
            provider=providers_tried[-1] if providers_tried else "",
            fallback_used=fallback_used,
            providers_tried=list(providers_tried),
            request_id=req_id,
            tenant_id=str(tenant_id) if tenant_id is not None else None,
            outcome="failed",
            health_skipped=len(skipped_unhealthy),
            skipped_unhealthy=list(skipped_unhealthy),
        )
        metrics.record(run)
        self._log_stream(
            request_id=req_id,
            tenant_id=tenant_id,
            provider=run.provider,
            model=model,
            stream_duration_ms=duration_ms,
            completion_tokens=0,
            finish_reason="error",
            outcome="failed",
        )
        if last_exc is not None:
            raise map_provider_exception(last_exc) from last_exc
        raise openai_error(
            status_code=502,
            message="No streaming provider available",
            type_="api_error",
            code="no_stream_provider",
        )

    async def _run_provider_stream(
        self,
        *,
        adapter: StreamingAdapter,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        request: Optional[Request],
        completion_id: str,
        created: int,
        started: float,
        request_id: str,
        tenant_id: Optional[str],
        fallback_used: bool,
        providers_tried: List[str],
        health_skipped: int = 0,
        skipped_unhealthy: Optional[List[str]] = None,
    ) -> AsyncIterator[str]:
        fingerprint = f"thtwaat-{adapter.name}"
        skipped_unhealthy = list(skipped_unhealthy or [])
        connect_timeout = _setting_float("STREAM_CONNECT_TIMEOUT", 10.0)
        first_token_timeout = _setting_float("STREAM_FIRST_TOKEN_TIMEOUT", 30.0)
        idle_timeout = _setting_float("STREAM_IDLE_TIMEOUT", 60.0)
        max_queued = _setting_int("STREAM_MAX_QUEUED_EVENTS", 256)

        queue: asyncio.Queue = asyncio.Queue(maxsize=max_queued)
        first_token_at: Optional[float] = None
        content_parts: List[str] = []
        streamed_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        finish_reason = "stop"
        cancelled = False
        role_emitted = False
        frames_emitted = False
        error_code: Optional[str] = None
        outcome = "completed"
        provider_started = time.perf_counter()

        async def _producer() -> None:
            nonlocal first_token_at, prompt_tokens, completion_tokens, finish_reason, error_code
            try:
                # Connect / open upstream with timeout
                agen = adapter.stream_chat(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                # First __anext__ establishes connection for HTTP adapters
                try:
                    first = await asyncio.wait_for(agen.__anext__(), timeout=connect_timeout)
                    await queue.put(("delta", first))
                    if first.content or (first.role and first.content is not None):
                        # role-only does not count as first token for fallback purposes
                        if first.content:
                            first_token_at = time.perf_counter()
                except StopAsyncIteration:
                    await queue.put(("done", None))
                    return
                except asyncio.TimeoutError as exc:
                    raise ProviderTimeoutError(
                        f"stream connect timeout after {connect_timeout}s"
                    ) from exc

                while True:
                    timeout = (
                        first_token_timeout
                        if first_token_at is None
                        else idle_timeout
                    )
                    try:
                        delta = await asyncio.wait_for(agen.__anext__(), timeout=timeout)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError as exc:
                        if first_token_at is None:
                            raise ProviderTimeoutError(
                                f"stream first-token timeout after {first_token_timeout}s"
                            ) from exc
                        raise ProviderTimeoutError(
                            f"stream idle timeout after {idle_timeout}s"
                        ) from exc

                    if delta.content and first_token_at is None:
                        first_token_at = time.perf_counter()
                    if delta.prompt_tokens is not None:
                        prompt_tokens = int(delta.prompt_tokens)
                    if delta.completion_tokens is not None:
                        completion_tokens = int(delta.completion_tokens)
                    if delta.finish_reason:
                        finish_reason = delta.finish_reason
                    await queue.put(("delta", delta))
                    if delta.done:
                        break
                await queue.put(("done", None))
            except Exception as exc:  # noqa: BLE001
                error_code = type(exc).__name__
                await queue.put(("error", exc))
            finally:
                try:
                    await adapter.cancel()
                except Exception:  # noqa: BLE001
                    pass

        task = asyncio.create_task(_producer())

        try:
            while True:
                if request is not None and await request.is_disconnected():
                    cancelled = True
                    outcome = "cancelled"
                    await adapter.cancel()
                    break

                try:
                    kind, payload = await queue.get()
                except Exception as exc:  # noqa: BLE001
                    raise StreamPreTokenError(adapter.name, exc) from exc

                if kind == "error":
                    exc = payload
                    assert isinstance(exc, BaseException)
                    # Fallback only when nothing has been sent to the client yet.
                    if not frames_emitted:
                        raise StreamPreTokenError(adapter.name, exc) from exc
                    # After streaming has started — emit SSE error, no fallback
                    outcome = "failed"
                    error_code = type(exc).__name__
                    mapped = map_provider_exception(exc)
                    err_body = mapped.detail if isinstance(mapped.detail, dict) else {}
                    err_code = (err_body.get("error") or {}).get("code") or "upstream_error"
                    yield format_sse(
                        {
                            "error": {
                                "message": str(exc),
                                "type": "api_error",
                                "code": err_code,
                            }
                        }
                    )
                    frames_emitted = True
                    yield format_sse("[DONE]")
                    break

                if kind == "done":
                    break

                delta: StreamDelta = payload
                try:
                    frames = list(
                        self._delta_to_frames(
                            delta=delta,
                            completion_id=completion_id,
                            created=created,
                            model=model,
                            fingerprint=fingerprint,
                            role_emitted=role_emitted,
                        )
                    )
                except Exception:
                    frames = []

                for frame, meta in frames:
                    if meta.get("role"):
                        role_emitted = True
                    if meta.get("content"):
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        content_parts.append(str(meta["content"]))
                        streamed_tokens += max(1, len(str(meta["content"]).split()))
                    if (
                        queue.full()
                        and request is not None
                        and await request.is_disconnected()
                    ):
                        cancelled = True
                        outcome = "cancelled"
                        await adapter.cancel()
                        raise StreamSlowClientError("slow client / full buffer")
                    yield frame
                    frames_emitted = True

                if delta.done:
                    break

            content = "".join(content_parts)
            if cancelled:
                pass
            else:
                if completion_tokens <= 0:
                    completion_tokens = streamed_tokens or (
                        max(1, len(content) // 4) if content else 0
                    )
                if prompt_tokens <= 0:
                    prompt_tokens = max(
                        1,
                        sum(len(str(m.get("content") or "")) for m in messages) // 4,
                    )
                usage = CompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                )
                if not role_emitted:
                    yield format_sse(
                        chunk_payload(
                            completion_id=completion_id,
                            created=created,
                            model=model,
                            delta=ChatCompletionChunkDelta(role="assistant", content=""),
                            system_fingerprint=fingerprint,
                        )
                    )
                yield format_sse(
                    chunk_payload(
                        completion_id=completion_id,
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
            provider_latency = (time.perf_counter() - provider_started) * 1000.0
            if cancelled:
                outcome = "cancelled"
            elif error_code and outcome != "failed":
                outcome = "failed"
            run = StreamRunMetrics(
                first_token_latency_ms=ttft,
                total_stream_duration_ms=duration_ms,
                streamed_tokens=streamed_tokens,
                cancelled=cancelled,
                error=error_code,
                provider=adapter.name,
                fallback_used=fallback_used,
                providers_tried=list(providers_tried),
                provider_latency_ms=provider_latency,
                finish_reason=finish_reason if not cancelled else "cancelled",
                request_id=request_id,
                tenant_id=str(tenant_id) if tenant_id is not None else None,
                outcome=outcome,
                health_skipped=health_skipped,
                skipped_unhealthy=list(skipped_unhealthy),
            )
            get_streaming_metrics().record(run)
            if outcome == "completed" and not cancelled and not error_code:
                _mark_provider_healthy(adapter.name)
            self._log_stream(
                request_id=request_id,
                tenant_id=tenant_id,
                provider=adapter.name,
                model=model,
                stream_duration_ms=duration_ms,
                completion_tokens=completion_tokens,
                finish_reason=run.finish_reason or finish_reason,
                outcome=outcome,
            )
            response = {
                "id": completion_id,
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
                completion_id=completion_id,
                model=model,
                provider=adapter.name,
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                finish_reason=finish_reason,
                cancelled=cancelled,
                response=response,
                metrics=run,
                fallback_used=fallback_used,
                providers_tried=list(providers_tried),
            )
        except StreamPreTokenError:
            raise
        except StreamSlowClientError:
            cancelled = True
            duration_ms = (time.perf_counter() - started) * 1000.0
            run = StreamRunMetrics(
                total_stream_duration_ms=duration_ms,
                streamed_tokens=streamed_tokens,
                cancelled=True,
                error="slow_client",
                provider=adapter.name,
                fallback_used=fallback_used,
                providers_tried=list(providers_tried),
                request_id=request_id,
                tenant_id=str(tenant_id) if tenant_id is not None else None,
                outcome="cancelled",
            )
            get_streaming_metrics().record(run)
            self.result = StreamEngineResult(
                completion_id=completion_id,
                model=model,
                provider=adapter.name,
                content="".join(content_parts),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                finish_reason="cancelled",
                cancelled=True,
                metrics=run,
                fallback_used=fallback_used,
                providers_tried=list(providers_tried),
            )
            return
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

    def _delta_to_frames(
        self,
        *,
        delta: StreamDelta,
        completion_id: str,
        created: int,
        model: str,
        fingerprint: str,
        role_emitted: bool,
    ):
        if delta.role and not role_emitted:
            yield (
                format_sse(
                    chunk_payload(
                        completion_id=completion_id,
                        created=created,
                        model=model,
                        delta=ChatCompletionChunkDelta(
                            role=delta.role, content=delta.content or ""
                        ),
                        system_fingerprint=fingerprint,
                    )
                ),
                {"role": True, "content": delta.content or None},
            )
            return

        if delta.content:
            if not role_emitted:
                yield (
                    format_sse(
                        chunk_payload(
                            completion_id=completion_id,
                            created=created,
                            model=model,
                            delta=ChatCompletionChunkDelta(role="assistant", content=""),
                            system_fingerprint=fingerprint,
                        )
                    ),
                    {"role": True},
                )
            yield (
                format_sse(
                    chunk_payload(
                        completion_id=completion_id,
                        created=created,
                        model=model,
                        delta=ChatCompletionChunkDelta(content=delta.content),
                        system_fingerprint=fingerprint,
                    )
                ),
                {"content": delta.content},
            )

    def _log_stream(
        self,
        *,
        request_id: str,
        tenant_id: Optional[str],
        provider: str,
        model: str,
        stream_duration_ms: float,
        completion_tokens: int,
        finish_reason: str,
        outcome: str,
    ) -> None:
        logger.info(
            "openai_compat.stream request_id=%s tenant_id=%s provider=%s model=%s "
            "stream_duration_ms=%.2f completion_tokens=%s finish_reason=%s outcome=%s",
            request_id,
            tenant_id,
            provider,
            model,
            stream_duration_ms,
            completion_tokens,
            finish_reason,
            outcome,
        )


async def resolve_stream_provider_name(
    *,
    model: str,
    provider: Optional[str],
) -> str:
    """Primary provider for a stream request (chain.providers[0])."""
    from app.openai_compat.stream_routing import resolve_stream_provider_chain

    chain = await resolve_stream_provider_chain(model=model, provider=provider)
    return chain.providers[0]
