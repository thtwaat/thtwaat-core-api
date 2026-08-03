"""Ollama inference provider (Sem03 W1 D2+)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import httpx

from app.config.settings import settings
from app.openai_compat.errors import wrap_httpx_error
from app.openai_compat.inference_adapter import (
    build_ollama_chat_payload,
    ollama_chat_to_openai_completion,
    probe_ollama,
)
from app.openai_compat.providers._common import model_entry, synthetic_embeddings
from app.openai_compat.providers.base import InferenceProvider, ProviderConfigError
from app.openai_compat.providers.registry import get_registry


class OllamaInferenceProvider(InferenceProvider):
    name = "ollama"

    def is_enabled(self) -> bool:
        return bool(getattr(settings, "INFERENCE_ENABLE_OLLAMA", True))

    def _base_url(self) -> str:
        url = (settings.OLLAMA_URL or "").rstrip("/")
        if not url:
            raise ProviderConfigError("OLLAMA_URL is not configured")
        return url

    def _timeout_seconds(self) -> float:
        raw = getattr(settings, "INFERENCE_OLLAMA_TIMEOUT_SECONDS", None)
        try:
            value = float(raw if raw is not None else 120.0)
        except (TypeError, ValueError):
            value = 120.0
        return max(1.0, value)

    def models(self) -> List[Dict[str, Any]]:
        return [
            model_entry("llama3.2", "ollama"),
            model_entry("qwen2.5-coder:3b", "ollama"),
            model_entry("mistral", "ollama"),
            model_entry("nomic-embed-text", "ollama"),
        ]

    async def health(self) -> Dict[str, Any]:
        if not self.is_enabled():
            return {"ok": False, "error": "disabled"}
        try:
            return probe_ollama(self._base_url())
        except ProviderConfigError as exc:
            return {"ok": False, "error": str(exc)}

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
            raise ProviderConfigError("ollama provider is disabled")
        base = self._base_url()
        payload = build_ollama_chat_payload(
            model=model,
            messages=list(messages),
            temperature=temperature,
            stream=False,
        )
        if max_tokens is not None:
            payload.setdefault("options", {})["num_predict"] = int(max_tokens)
        timeout = self._timeout_seconds()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{base}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, TimeoutError) as exc:
            raise wrap_httpx_error(exc, provider=self.name) from exc
        return ollama_chat_to_openai_completion(data, model=model)

    async def embeddings(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.is_enabled():
            raise ProviderConfigError("ollama provider is disabled")
        # Day 2: synthetic embeddings interface (live embed Week 2+)
        return synthetic_embeddings(model=model, input=input, dims=8)


get_registry().register("ollama", OllamaInferenceProvider)
