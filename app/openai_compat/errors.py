"""OpenAI-shaped inference error mapping (Sem03 W1 D4)."""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status


def openai_error(
    *,
    status_code: int,
    message: str,
    type_: str,
    code: str,
    param: Optional[str] = None,
) -> HTTPException:
    body: Dict[str, Any] = {
        "error": {
            "message": message,
            "type": type_,
            "code": code,
        }
    }
    if param is not None:
        body["error"]["param"] = param
    return HTTPException(status_code=status_code, detail=body)


def model_not_found(model_id: str) -> HTTPException:
    return openai_error(
        status_code=status.HTTP_404_NOT_FOUND,
        message=f"The model '{model_id}' does not exist",
        type_="invalid_request_error",
        code="model_not_found",
        param="model",
    )


def unknown_provider(name: str) -> HTTPException:
    return openai_error(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=f"Unknown or disabled provider '{name}'",
        type_="invalid_request_error",
        code="unknown_provider",
        param="provider",
    )


def no_healthy_provider(model_id: str, skipped: Optional[list[str]] = None) -> HTTPException:
    skipped_s = ", ".join(skipped) if skipped else "(none)"
    return openai_error(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        message=(
            f"No healthy provider available for model '{model_id}' "
            f"(skipped unhealthy: {skipped_s})"
        ),
        type_="api_error",
        code="no_healthy_provider",
    )


def wrap_httpx_error(exc: BaseException, *, provider: str):
    """Normalize httpx failures into typed provider errors (no HTTPException yet)."""
    from app.openai_compat.providers.base import (
        InferenceProviderError,
        ProviderTimeoutError,
        ProviderUpstreamError,
    )

    if isinstance(exc, InferenceProviderError):
        return exc
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return ProviderTimeoutError(
            f"Provider '{provider}' timed out: {exc}",
            provider=provider,
        )
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code if exc.response is not None else None
        return ProviderUpstreamError(
            f"Provider '{provider}' HTTP {code}: {exc}",
            provider=provider,
            status_code=code,
        )
    if isinstance(exc, httpx.HTTPError):
        return ProviderUpstreamError(
            f"Provider '{provider}' transport error: {exc}",
            provider=provider,
        )
    return InferenceProviderError(f"Provider '{provider}' failed: {exc}")


def map_provider_exception(exc: BaseException) -> HTTPException:
    """
    Map provider / transport failures to OpenAI-shaped HTTP errors.

    Taxonomy (Day 4):
      - ProviderTimeoutError / httpx timeout → 504 upstream_timeout
      - ProviderUpstreamError / httpx HTTP   → 502 upstream_error
      - ProviderConfigError                  → 502 provider_config_error
      - ProviderNotFoundError                → 400 unknown_provider
      - other InferenceProviderError         → 502 upstream_error
      - bare httpx timeout / HTTP            → same as above
      - everything else                      → 502 upstream_error
    """
    from app.openai_compat.providers.base import (
        InferenceProviderError,
        ProviderConfigError,
        ProviderNotFoundError,
        ProviderTimeoutError,
        ProviderUpstreamError,
    )

    if isinstance(exc, HTTPException):
        return exc

    if isinstance(exc, ProviderTimeoutError) or isinstance(
        exc, (httpx.TimeoutException, TimeoutError)
    ):
        return openai_error(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            message=f"Upstream inference timed out: {exc}",
            type_="api_error",
            code="upstream_timeout",
        )

    if isinstance(exc, ProviderNotFoundError):
        return unknown_provider(str(exc))

    if isinstance(exc, ProviderConfigError):
        return openai_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            message=f"Provider configuration error: {exc}",
            type_="api_error",
            code="provider_config_error",
        )

    if isinstance(exc, ProviderUpstreamError) or isinstance(exc, httpx.HTTPStatusError):
        return openai_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            message=f"Upstream inference failed: {exc}",
            type_="api_error",
            code="upstream_error",
        )

    if isinstance(exc, httpx.HTTPError):
        return openai_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            message=f"Upstream inference failed: {exc}",
            type_="api_error",
            code="upstream_error",
        )

    if isinstance(exc, InferenceProviderError):
        return openai_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            message=f"Upstream inference failed: {exc}",
            type_="api_error",
            code="upstream_error",
        )

    return openai_error(
        status_code=status.HTTP_502_BAD_GATEWAY,
        message=f"Upstream inference failed: {exc}",
        type_="api_error",
        code="upstream_error",
    )
