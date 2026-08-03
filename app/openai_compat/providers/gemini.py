"""Gemini inference provider (Sem03 W1 D2)."""
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


class GeminiInferenceProvider(InferenceProvider):
    name = "gemini"

    def is_enabled(self) -> bool:
        return bool(getattr(settings, "INFERENCE_ENABLE_GEMINI", True))

    def models(self) -> List[Dict[str, Any]]:
        return [
            model_entry("gemini-1.5-flash", "google"),
            model_entry("gemini-1.5-pro", "google"),
        ]

    async def health(self) -> Dict[str, Any]:
        if not self.is_enabled():
            return {"ok": False, "error": "disabled"}
        configured = bool(settings.GEMINI_API_KEY)
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
            raise ProviderConfigError("gemini provider is disabled")
        if not settings.GEMINI_API_KEY:
            raise ProviderConfigError("GEMINI_API_KEY is not configured")
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
            raise ProviderConfigError("gemini provider is disabled")
        if not settings.GEMINI_API_KEY:
            raise ProviderConfigError("GEMINI_API_KEY is not configured")
        return synthetic_embeddings(model=model, input=input)


get_registry().register("gemini", GeminiInferenceProvider)
