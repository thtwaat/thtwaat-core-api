"""Inference provider interface (Semester 03 Week 1 Day 2+)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Union


class InferenceProviderError(Exception):
    """Base error for inference providers."""


class ProviderNotFoundError(InferenceProviderError):
    """Provider name is not registered or not enabled."""


class ProviderConfigError(InferenceProviderError):
    """Provider is enabled but missing required configuration."""


class ProviderTimeoutError(InferenceProviderError):
    """Upstream provider exceeded the configured timeout."""

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider


class ProviderUpstreamError(InferenceProviderError):
    """Upstream provider returned a transport / HTTP failure."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class InferenceProvider(ABC):
    """Standard Sem03 provider surface for /v1 routing."""

    name: str = "base"

    @abstractmethod
    def is_enabled(self) -> bool:
        """Env / config gate — disabled providers are hidden from catalogs."""

    @abstractmethod
    async def chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Return an OpenAI-shaped chat.completion dict."""

    @abstractmethod
    async def embeddings(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Return an OpenAI-shaped embeddings object."""

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """Soft health — never raise; return {ok, ...}."""

    @abstractmethod
    def models(self) -> List[Dict[str, Any]]:
        """OpenAI model objects this provider contributes to GET /v1/models."""

    async def stream_chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Optional token stream (Sem03 W2+).

        Default: not implemented — use StreamingAdapter via StreamEngine instead.
        """
        raise ProviderConfigError(f"Provider '{self.name}' does not support stream_chat()")
        yield  # pragma: no cover — keep as async generator type
