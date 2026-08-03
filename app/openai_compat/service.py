"""Completions service — OpenAI-compatible chat completions (Week 2 Day 1+2)."""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.openai_compat.cache import OpenAICompatCache, fingerprint_completion_request
from app.openai_compat.dependencies import CompletionsPrincipal
from app.openai_compat.models import OpenAICompletionLog
from app.openai_compat.repository import CompletionLogRepository
from app.openai_compat.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    CompletionUsage,
)
from app.openai_compat.stub import stub_complete

CacheStatus = Literal["HIT", "MISS", "BYPASS"]


class CompletionsService:
    def __init__(self, db: Session, cache: OpenAICompatCache | None = None):
        self.db = db
        self.repo = CompletionLogRepository(db)
        self.cache = cache or OpenAICompatCache()

    def _response_cacheable(self, body: ChatCompletionRequest) -> bool:
        if not self.cache.enabled or not self.cache.responses_enabled:
            return False
        if body.stream:
            return False
        # Only cache fully deterministic requests
        return body.temperature is not None and float(body.temperature) == 0.0

    def _fingerprint(self, principal: CompletionsPrincipal, body: ChatCompletionRequest) -> str:
        return fingerprint_completion_request(
            {
                "company_id": str(principal.company_id),
                "model": body.model,
                "messages": [m.model_dump() for m in body.messages],
                "temperature": body.temperature,
                "max_tokens": body.max_tokens,
                "top_p": body.top_p,
                "stop": body.stop,
                "provider": body.provider,
                "inference": (settings.OPENAI_COMPAT_INFERENCE or "stub").strip().lower(),
            }
        )

    async def create_completion(
        self,
        principal: CompletionsPrincipal,
        body: ChatCompletionRequest,
    ) -> Tuple[ChatCompletionResponse, CacheStatus]:
        if body.stream:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "message": (
                            "Use the streaming path via the router with stream=true "
                            "(internal: call stream_completion)."
                        ),
                        "type": "invalid_request_error",
                        "code": "stream_use_sse_path",
                    }
                },
            )

        if body.n is not None and body.n != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "message": "Only n=1 is supported.",
                        "type": "invalid_request_error",
                        "code": "n_not_supported",
                    }
                },
            )

        from app.openai_compat.prompt_guard import assert_safe_completion_messages

        assert_safe_completion_messages(body.messages)

        cacheable = self._response_cacheable(body)
        fp: Optional[str] = None
        if cacheable:
            fp = self._fingerprint(principal, body)
            cached = self.cache.get_completion(principal.company_id, fp)
            if cached is not None:
                return ChatCompletionResponse.model_validate(cached), "HIT"

        started = time.perf_counter()
        completion_id = f"chatcmpl_{uuid.uuid4().hex}"
        mode = (settings.OPENAI_COMPAT_INFERENCE or "stub").strip().lower()
        provider = "stub"
        content = ""
        prompt_tokens = 0
        completion_tokens = 0
        finish_reason = "stop"
        status_label = "succeeded"
        error_detail = None

        try:
            if mode == "gateway":
                content, prompt_tokens, completion_tokens, provider, finish_reason = (
                    await self._via_gateway(principal, body)
                )
            else:
                content, prompt_tokens, completion_tokens = stub_complete(
                    body.messages, model=body.model
                )
                provider = "stub"
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — map provider failures to OpenAI-shaped errors
            from app.openai_compat.errors import map_provider_exception

            status_label = "failed"
            error_detail = str(exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._persist_log(
                principal=principal,
                completion_id=completion_id,
                body=body,
                provider=provider,
                content=None,
                prompt_tokens=0,
                completion_tokens=0,
                finish_reason=None,
                latency_ms=latency_ms,
                status=status_label,
                error_detail=error_detail,
            )
            self._notify_completion(
                principal=principal,
                completion_id=completion_id,
                body=body,
                outcome="failed",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                error=error_detail,
                provider=provider,
            )
            raise map_provider_exception(exc) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        self._persist_log(
            principal=principal,
            completion_id=completion_id,
            body=body,
            provider=provider,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            status=status_label,
            error_detail=None,
        )

        # Day 5 — usage meter + cost (skip on cache HIT; gateway path meters here only)
        usage_summary: Dict[str, Any] = {}
        try:
            from app.openai_compat.usage import record_completion_usage

            usage_summary = record_completion_usage(
                self.db,
                principal,
                provider=provider,
                model=body.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                completion_id=completion_id,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            # Soft-fail metering must not break completions
            import logging

            logging.getLogger(__name__).warning("usage hook failed: %s", exc)

        self._notify_completion(
            principal=principal,
            completion_id=completion_id,
            body=body,
            outcome="succeeded",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            error=None,
            provider=provider,
            estimated_cost=usage_summary.get("estimated_cost"),
        )

        created = int(time.time())
        response = ChatCompletionResponse(
            id=completion_id,
            created=created,
            model=body.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            system_fingerprint=f"thtwaat-{provider}",
        )

        cache_status: CacheStatus = "BYPASS"
        if cacheable and fp is not None:
            self.cache.set_completion(
                principal.company_id,
                fp,
                response.model_dump(),
            )
            cache_status = "MISS"

        return response, cache_status

    async def build_stream_material(
        self,
        principal: CompletionsPrincipal,
        body: ChatCompletionRequest,
    ):
        """
        Week 3 Day 4 — prepare full completion before SSE.
        Idempotency can store `material.response` before the first byte is sent.
        """
        from app.openai_compat.streaming import StreamMaterial, stub_stream_pieces

        if body.n is not None and body.n != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "message": "Only n=1 is supported.",
                        "type": "invalid_request_error",
                        "code": "n_not_supported",
                    }
                },
            )

        from app.openai_compat.prompt_guard import assert_safe_completion_messages

        assert_safe_completion_messages(body.messages)

        started = time.perf_counter()
        completion_id = f"chatcmpl_{uuid.uuid4().hex}"
        mode = (settings.OPENAI_COMPAT_INFERENCE or "stub").strip().lower()
        provider = "stub"
        content = ""
        prompt_tokens = 0
        completion_tokens = 0
        finish_reason = "stop"
        pieces: List[str] = []

        try:
            if mode == "gateway":
                content, prompt_tokens, completion_tokens, provider, finish_reason = (
                    await self._via_gateway(principal, body)
                )
                from app.openai_compat.streaming import iter_text_pieces

                pieces = list(iter_text_pieces(content))
            else:
                content, prompt_tokens, completion_tokens, pieces = stub_stream_pieces(
                    body.messages, model=body.model
                )
                provider = "stub"
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            from app.openai_compat.errors import map_provider_exception

            latency_ms = int((time.perf_counter() - started) * 1000)
            self._persist_log(
                principal=principal,
                completion_id=completion_id,
                body=body,
                provider=provider,
                content=None,
                prompt_tokens=0,
                completion_tokens=0,
                finish_reason=None,
                latency_ms=latency_ms,
                status="failed",
                error_detail=str(exc),
            )
            self._notify_completion(
                principal=principal,
                completion_id=completion_id,
                body=body,
                outcome="failed",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                error=str(exc),
                provider=provider,
            )
            raise map_provider_exception(exc) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        self._persist_log(
            principal=principal,
            completion_id=completion_id,
            body=body,
            provider=provider,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            status="succeeded",
            error_detail=None,
        )
        try:
            from app.openai_compat.usage import record_completion_usage

            usage_summary = record_completion_usage(
                self.db,
                principal,
                provider=provider,
                model=body.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                completion_id=completion_id,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning("usage hook failed (stream): %s", exc)
            usage_summary = {}

        self._notify_completion(
            principal=principal,
            completion_id=completion_id,
            body=body,
            outcome="succeeded",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            error=None,
            provider=provider,
            estimated_cost=usage_summary.get("estimated_cost") if usage_summary else None,
        )

        created = int(time.time())
        response = ChatCompletionResponse(
            id=completion_id,
            created=created,
            model=body.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            system_fingerprint=f"thtwaat-{provider}",
        )
        return StreamMaterial(
            completion_id=completion_id,
            model=body.model,
            content=content,
            pieces=pieces,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            provider=provider,
            finish_reason=finish_reason,
            response=response.model_dump(),
        )

    async def stream_completion(
        self,
        principal: CompletionsPrincipal,
        body: ChatCompletionRequest,
    ):
        """Yield SSE frames after material is prepared (no idempotency here)."""
        from app.openai_compat.streaming import aiter_sse_from_material

        material = await self.build_stream_material(principal, body)
        async for frame in aiter_sse_from_material(material):
            yield frame

    def _notify_completion(
        self,
        *,
        principal: CompletionsPrincipal,
        completion_id: str,
        body: ChatCompletionRequest,
        outcome: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        error: Optional[str],
        provider: str,
        estimated_cost: Optional[float] = None,
    ) -> None:
        """Week 3 Day 1 — enqueue completion webhooks (fail-open)."""
        if not getattr(settings, "OPENAI_COMPAT_WEBHOOKS_ENABLED", True):
            return
        try:
            from app.openai_compat.events import (
                EVENT_COMPLETION_FAILED,
                EVENT_COMPLETION_SUCCEEDED,
                build_completion_event_data,
            )
            from app.openai_compat.notify import enqueue_completion_webhooks

            event = (
                EVENT_COMPLETION_SUCCEEDED
                if outcome == "succeeded"
                else EVENT_COMPLETION_FAILED
            )
            data = build_completion_event_data(
                completion_id=completion_id,
                model=body.model,
                status=outcome,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                error=error,
                provider=provider,
                estimated_cost=estimated_cost,
            )
            enqueue_completion_webhooks(self.db, principal.company_id, event, data)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning("completion webhook notify failed: %s", exc)

    async def _via_gateway(
        self,
        principal: CompletionsPrincipal,
        body: ChatCompletionRequest,
    ) -> tuple[str, int, int, str, str]:
        from app.openai_compat.inference_routing_service import InferenceRoutingService

        messages: List[Dict[str, Any]] = []
        for m in body.messages:
            payload: Dict[str, Any] = {"role": m.role, "content": m.content}
            if m.name:
                payload["name"] = m.name
            messages.append(payload)

        routing = InferenceRoutingService()
        try:
            result, decision = await routing.chat(
                model=body.model,
                messages=messages,
                provider=body.provider,
                temperature=body.temperature if body.temperature is not None else 0.7,
                max_tokens=body.max_tokens,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            from app.openai_compat.errors import map_provider_exception

            raise map_provider_exception(exc) from exc

        choices = (result or {}).get("choices") or []
        content = ""
        finish = "stop"
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
            finish = choices[0].get("finish_reason") or "stop"
        usage = (result or {}).get("usage") or {}
        return (
            content,
            int(usage.get("prompt_tokens") or 0),
            int(usage.get("completion_tokens") or 0),
            decision.provider_name,
            finish,
        )

    def _persist_log(
        self,
        *,
        principal: CompletionsPrincipal,
        completion_id: str,
        body: ChatCompletionRequest,
        provider: str,
        content: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        finish_reason: str | None,
        latency_ms: int,
        status: str,
        error_detail: str | None,
    ) -> None:
        row = OpenAICompletionLog(
            company_id=principal.company_id,
            api_key_id=principal.api_key_id,
            agent_id=principal.agent_id,
            completion_id=completion_id,
            model=body.model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason=finish_reason,
            request_messages=[m.model_dump() for m in body.messages],
            response_content=content,
            latency_ms=latency_ms,
            status=status,
            error_detail=error_detail,
        )
        self.repo.create(row)
