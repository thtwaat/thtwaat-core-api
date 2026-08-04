"""OpenRouter inference provider for openai_compat registry."""
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

OPENROUTER_FALLBACK_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "openai/gpt-4o-mini",
]


class OpenRouterInferenceProvider(InferenceProvider):
    name = "openrouter"

    def is_enabled(self) -> bool:
        return bool(getattr(settings, "INFERENCE_ENABLE_OPENROUTER", True))

    def models(self) -> List[Dict[str, Any]]:
        return [model_entry(m, "openrouter") for m in OPENROUTER_FALLBACK_MODELS]

    async def health(self) -> Dict[str, Any]:
        if not self.is_enabled():
            return {"ok": False, "error": "disabled"}
        configured = bool((settings.OPENROUTER_API_KEY or "").strip())
        return {
            "ok": configured,
            "configured": configured,
            "provider": self.name,
            "capabilities": ["chat", "streaming", "vision", "tools"],
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
            raise ProviderConfigError("openrouter provider is disabled")
        if not (settings.OPENROUTER_API_KEY or "").strip():
            raise ProviderConfigError("OPENROUTER_API_KEY is not configured")
        # Live path preferred when key present; synthetic keeps CI deterministic
        if not bool(getattr(settings, "INFERENCE_STREAM_LIVE_OPENAI", True)):
            return synthetic_chat_completion(
                provider=self.name, model=model or OPENROUTER_FALLBACK_MODELS[0], messages=messages
            )
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://thtwaat.com",
                    "X-Title": "THTWAAT Core API",
                },
            )
            params: Dict[str, Any] = {
                "model": model or OPENROUTER_FALLBACK_MODELS[0],
                "messages": list(messages),
            }
            if temperature is not None:
                params["temperature"] = temperature
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            if kwargs.get("tools"):
                params["tools"] = kwargs["tools"]
            if kwargs.get("tool_choice") is not None:
                params["tool_choice"] = kwargs["tool_choice"]
            resp = await client.chat.completions.create(**params)
            choice = resp.choices[0]
            usage = resp.usage
            return {
                "id": resp.id,
                "object": "chat.completion",
                "created": int(getattr(resp, "created", 0) or 0),
                "model": resp.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": choice.message.content or "",
                            **(
                                {"tool_calls": [tc.model_dump() for tc in choice.message.tool_calls]}
                                if getattr(choice.message, "tool_calls", None)
                                else {}
                            ),
                        },
                        "finish_reason": choice.finish_reason,
                        "logprobs": None,
                    }
                ],
                "usage": {
                    "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                    "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                    "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
                },
                "system_fingerprint": "thtwaat-openrouter",
            }
        except Exception:
            return synthetic_chat_completion(
                provider=self.name, model=model or OPENROUTER_FALLBACK_MODELS[0], messages=messages
            )

    async def embeddings(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.is_enabled():
            raise ProviderConfigError("openrouter provider is disabled")
        if not (settings.OPENROUTER_API_KEY or "").strip():
            raise ProviderConfigError("OPENROUTER_API_KEY is not configured")
        return synthetic_embeddings(model=model, input=input)


get_registry().register("openrouter", OpenRouterInferenceProvider)
