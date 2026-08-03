"""Inference provider interface (Semester 03 Week 1 Day 2)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Union


class InferenceProviderError(Exception):
    """Base error for inference providers."""


class ProviderNotFoundError(InferenceProviderError):
    """Provider name is not registered or not enabled."""


class ProviderConfigError(InferenceProviderError):
    """Provider is enabled but missing required configuration."""


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
