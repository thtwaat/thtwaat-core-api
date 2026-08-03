"""Anthropic inference provider (Sem03 W1 D2)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from app.config.settings import settings
from app.openai_compat.providers._common import (
    model_entry,
    synthetic_chat_completion,
    synthetic_embeddings,
)
from app.openai_compat.providers.base import InferenceProvider, ProviderConfigError
from app.openai_compat.providers.registry import get_registry


class AnthropicInferenceProvider(InferenceProvider):
    name = "anthropic"

    def is_enabled(self) -> bool:
        return bool(getattr(settings, "INFERENCE_ENABLE_ANTHROPIC", True))

    def models(self) -> List[Dict[str, Any]]:
        return [
            model_entry("claude-3-5-sonnet", "anthropic"),
            model_entry("claude-3-5-haiku", "anthropic"),
        ]

    async def health(self) -> Dict[str, Any]:
        if not self.is_enabled():
            return {"ok": False, "error": "disabled"}
        configured = bool(settings.ANTHROPIC_API_KEY)
        return {"ok": configured, "configured": configured, "provider": self.name}

    async def chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.is_enabled():
            raise ProviderConfigError("anthropic provider is disabled")
        if not settings.ANTHROPIC_API_KEY:
            raise ProviderConfigError("ANTHROPIC_API_KEY is not configured")
        return synthetic_chat_completion(
            provider=self.name, model=model, messages=messages
        )

    async def embeddings(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.is_enabled():
            raise ProviderConfigError("anthropic provider is disabled")
        raise ProviderConfigError("anthropic embeddings are not supported on this surface")


get_registry().register("anthropic", AnthropicInferenceProvider)
