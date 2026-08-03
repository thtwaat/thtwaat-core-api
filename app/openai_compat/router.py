"""OpenAI-compatible HTTP surface — root /v1 (Week 2–3)."""
from __future__ import annotations

from typing import Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.openai_compat.dependencies import CompletionsPrincipal, resolve_completions_principal
from app.openai_compat.idempotency import (
    IdempotencyStore,
    hash_completion_body,
    validate_idempotency_key,
)
from app.openai_compat.models_service import ModelsService
from app.openai_compat.rate_limit import OpenAICompatRateLimiter
from app.openai_compat.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelObject,
    ModelsListResponse,
)
from app.openai_compat.service import CompletionsService
from app.openai_compat.usage import usage_analytics_payload

router = APIRouter(prefix="/v1", tags=["OpenAI Compatible"])


@router.get(
    "/usage",
    summary="Tenant usage analytics (THTWAAT extension)",
    openapi_extra={
        "security": [{"AgentAPIKey": []}],
        "x-thtwaat-course": "semester-02/week-02/day-05",
    },
)
def get_usage_analytics(
    response: Response,
    principal: CompletionsPrincipal = Depends(resolve_completions_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Monthly meter + 30-day daily token series for the authenticated tenant."""
    limiter = OpenAICompatRateLimiter(db)
    decision = limiter.enforce(principal.company_id, scope="models")
    limiter.apply_headers(response, decision)
    return usage_analytics_payload(db, principal.company_id)


@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="List models (OpenAI-compatible, Redis-cached)",
    openapi_extra={
        "security": [{"AgentAPIKey": []}],
        "x-thtwaat-course": "semester-02/week-02/day-02",
    },
)
def list_models(
    response: Response,
    principal: CompletionsPrincipal = Depends(resolve_completions_principal),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=100, description="Page size (1–100)"),
    offset: int = Query(0, ge=0, description="Items to skip"),
) -> ModelsListResponse:
    limiter = OpenAICompatRateLimiter(db)
    decision = limiter.enforce(principal.company_id, scope="models")
    limiter.apply_headers(response, decision)

    payload, cache_status = ModelsService(db).list_models(
        principal.company_id, limit=limit, offset=offset
    )
    response.headers["X-Cache"] = cache_status
    return payload


@router.get(
    "/models/{model_id}",
    response_model=ModelObject,
    summary="Retrieve model metadata (OpenAI-compatible, Redis-cached)",
    openapi_extra={
        "security": [{"AgentAPIKey": []}],
        "x-thtwaat-course": "semester-02/week-02/day-02",
    },
)
def retrieve_model(
    model_id: str,
    response: Response,
    principal: CompletionsPrincipal = Depends(resolve_completions_principal),
    db: Session = Depends(get_db),
) -> ModelObject:
    limiter = OpenAICompatRateLimiter(db)
    decision = limiter.enforce(principal.company_id, scope="models")
    limiter.apply_headers(response, decision)

    payload, cache_status = ModelsService(db).get_model(principal.company_id, model_id)
    response.headers["X-Cache"] = cache_status
    return payload


@router.post(
    "/chat/completions",
    response_model=None,
    summary="Create chat completion (OpenAI-compatible)",
    responses={
        401: {
            "description": "Missing or invalid API key",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "error": {
                                "message": "Missing API key",
                                "type": "invalid_request_error",
                                "code": "missing_api_key",
                            }
                        }
                    }
                }
            },
        },
        400: {
            "description": "Invalid option (e.g. Idempotency-Key with stream=true)",
        },
        409: {
            "description": "Idempotency conflict (key reuse or in-progress)",
        },
        429: {
            "description": "Tenant rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "error": {
                                "message": "Rate limit exceeded for plan 'free' (rpm).",
                                "type": "rate_limit_error",
                                "code": "rate_limit_exceeded",
                                "plan": "free",
                                "limit": 20,
                                "window": "rpm",
                            }
                        }
                    }
                }
            },
            "headers": {
                "Retry-After": {
                    "description": "Seconds until the current window resets",
                    "schema": {"type": "integer"},
                }
            },
        },
    },
    openapi_extra={
        "security": [{"AgentAPIKey": []}],
        "x-thtwaat-course": "semester-02/week-03/day-03",
        "parameters": [
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": False,
                "schema": {"type": "string", "maxLength": 256},
                "description": (
                    "Optional (non-stream only). Retries with the same key + body replay "
                    "the stored response. Same key + different body → 409. "
                    "Not supported with stream=true (Day 4)."
                ),
            }
        ],
    },
)
async def create_chat_completion(
    body: ChatCompletionRequest,
    response: Response,
    principal: CompletionsPrincipal = Depends(resolve_completions_principal),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> Union[ChatCompletionResponse, StreamingResponse]:
    """
    OpenAI SDK compatible completions.

    JSON when stream=false; SSE (`text/event-stream`) when stream=true (Week 3 Day 3).
    """
    if body.stream and idempotency_key is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": (
                        "Idempotency-Key is not supported with stream=true yet. "
                        "Omit the header or set stream=false."
                    ),
                    "type": "invalid_request_error",
                    "code": "idempotency_stream_unsupported",
                }
            },
        )

    limiter = OpenAICompatRateLimiter(db)
    decision = limiter.enforce(principal.company_id, scope="completions")

    if body.stream:
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Cache": "BYPASS",
        }
        headers.update(OpenAICompatRateLimiter.header_map(decision))
        return StreamingResponse(
            CompletionsService(db).stream_completion(principal, body),
            media_type="text/event-stream",
            headers=headers,
        )

    store = IdempotencyStore()
    key: Optional[str] = None
    request_hash: Optional[str] = None

    if idempotency_key is not None:
        key = validate_idempotency_key(idempotency_key)
        request_hash = hash_completion_body(
            {
                "company_id": str(principal.company_id),
                "model": body.model,
                "messages": [m.model_dump() for m in body.messages],
                "temperature": body.temperature,
                "max_tokens": body.max_tokens,
                "top_p": body.top_p,
                "stop": body.stop,
                "provider": body.provider,
                "n": body.n,
                "stream": body.stream,
                "user": body.user,
            }
        )
        action, record = store.begin_or_lookup(
            company_id=principal.company_id,
            idempotency_key=key,
            request_hash=request_hash,
        )
        if action == "replay" and record is not None and record.response is not None:
            response.headers["Idempotent-Replayed"] = "true"
            response.headers["X-Cache"] = "BYPASS"
            limiter.apply_headers(response, decision)
            return ChatCompletionResponse.model_validate(record.response)

    limiter.apply_headers(response, decision)

    try:
        result, cache_status = await CompletionsService(db).create_completion(principal, body)
    except Exception:
        if key is not None:
            store.abandon(company_id=principal.company_id, idempotency_key=key)
        raise

    if key is not None and request_hash is not None:
        store.complete(
            company_id=principal.company_id,
            idempotency_key=key,
            request_hash=request_hash,
            response=result.model_dump(),
            http_status=200,
        )
        response.headers["Idempotent-Replayed"] = "false"
    response.headers["X-Cache"] = cache_status
    return result
