"""OpenRouter SSE streaming — OpenAI-compatible base URL."""
from __future__ import annotations

from typing import Dict

from app.config.settings import settings
from app.openai_compat.providers.openai_stream import OpenAIStreamingAdapter


class OpenRouterStreamingAdapter(OpenAIStreamingAdapter):
    name = "openrouter"
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self) -> None:
        super().__init__(base_url=self.BASE_URL)

    def _provider_enabled(self) -> bool:
        return bool(getattr(settings, "INFERENCE_ENABLE_OPENROUTER", True))

    def _resolve_api_key(self) -> str:
        return (settings.OPENROUTER_API_KEY or "").strip()

    def _auth_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thtwaat.com",
            "X-Title": "THTWAAT Core API",
        }
