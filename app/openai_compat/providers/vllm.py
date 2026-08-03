"""vLLM stub inference provider (Sem03 W1 D2)."""
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


class VllmInferenceProvider(InferenceProvider):
    """Stub backend — enabled only when INFERENCE_ENABLE_VLLM=true."""

    name = "vllm"

    def is_enabled(self) -> bool:
        return bool(getattr(settings, "INFERENCE_ENABLE_VLLM", False))

    def models(self) -> List[Dict[str, Any]]:
        return [
            model_entry("vllm-stub-mini", "vllm"),
        ]

    async def health(self) -> Dict[str, Any]:
        if not self.is_enabled():
            return {"ok": False, "error": "disabled"}
        base = (getattr(settings, "VLLM_BASE_URL", None) or "").strip()
        return {
            "ok": True,
            "configured": bool(base),
            "stub": True,
            "provider": self.name,
            "base_url": base or None,
        }

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
            raise ProviderConfigError("vllm provider is disabled")
        return synthetic_chat_completion(
            provider=self.name,
            model=model,
            messages=messages,
            content=f"[vllm-stub] echo for {model}",
        )

    async def embeddings(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.is_enabled():
            raise ProviderConfigError("vllm provider is disabled")
        return synthetic_embeddings(model=model, input=input)


get_registry().register("vllm", VllmInferenceProvider)
