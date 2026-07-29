"""
app/ai/providers/openrouter.py
OpenRouter Provider - Real SDK Implementation

OpenRouter exposes an OpenAI-compatible REST API at:
    https://openrouter.ai/api/v1

We reuse the already-installed `openai` SDK and point it at that base URL.
This means zero extra dependencies and full support for every model
OpenRouter aggregates (Claude, GPT, Llama, Mistral, Gemini, etc.).
"""
import logging
from typing import List, Dict, Any, Optional
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Free-tier / low-cost fallback chain — ordered by reliability
OPENROUTER_FALLBACK_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-1b-it:free",
    "qwen/qwen-2.5-7b-instruct:free",
]


class OpenRouterProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self._client = None

    def _get_client(self):
        """Lazily initialize an AsyncOpenAI client pointed at OpenRouter."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                if not self.api_key:
                    raise ValueError("OPENROUTER_API_KEY is not configured in .env")
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=OPENROUTER_BASE_URL,
                    default_headers={
                        # Required by OpenRouter — identifies your app
                        "HTTP-Referer": "https://thtwaat.com",
                        "X-Title": "THTWAAT Core API",
                    },
                )
            except ImportError:
                raise RuntimeError(
                    "openai package is not installed. Run: pip install openai"
                )
        return self._client

    def _resolve_model(self, model: str) -> str:
        """Return model as-is; fallback to first free model if empty."""
        if not model:
            return OPENROUTER_FALLBACK_MODELS[0]
        return model

    async def chat(
        self, messages: List[Dict[str, str]], model: str, **kwargs
    ) -> AIProviderResponse:
        client = self._get_client()
        resolved_model = self._resolve_model(model)
        logger.info(f"OpenRouter Provider: Generating chat using {resolved_model}")

        async def _call(m: str) -> AIProviderResponse:
            params: Dict[str, Any] = {
                "model": m,
                "messages": messages,
            }
            if kwargs.get("temperature") is not None:
                params["temperature"] = kwargs["temperature"]
            if kwargs.get("max_tokens") is not None:
                params["max_tokens"] = kwargs["max_tokens"]

            response = await client.chat.completions.create(**params)

            content = response.choices[0].message.content or ""
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            model_used = response.model or m

            return AIProviderResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=model_used,
                provider_response_id=response.id or "",
            )

        try:
            return await _call(resolved_model)

        except Exception as e:
            logger.error(
                f"OpenRouter chat error (model={resolved_model}): {str(e)}"
            )
            # Automatic fallback to next free model
            for fallback_model in OPENROUTER_FALLBACK_MODELS:
                if fallback_model == resolved_model:
                    continue
                logger.info(f"OpenRouter: Falling back to {fallback_model}")
                try:
                    return await _call(fallback_model)
                except Exception as fb_err:
                    logger.error(
                        f"OpenRouter fallback {fallback_model} failed: {str(fb_err)}"
                    )
                    continue
            raise Exception(f"OpenRouter Provider Error: {str(e)}")

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        """Single prompt generation via chat completions endpoint."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages=messages, model=model, **kwargs)

    async def models(self) -> List[str]:
        """
        Fetch live model list from OpenRouter.
        OpenRouter's /models endpoint returns all available models.
        """
        try:
            import httpx
            async with httpx.AsyncClient() as http:
                r = await http.get(
                    f"{OPENROUTER_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                )
                r.raise_for_status()
                data = r.json()
                model_ids = [m["id"] for m in data.get("data", [])]
                return model_ids[:50] if model_ids else OPENROUTER_FALLBACK_MODELS
        except Exception as e:
            logger.warning(
                f"OpenRouter models list failed, using defaults: {str(e)}"
            )
            return OPENROUTER_FALLBACK_MODELS

    async def health(self) -> bool:
        """Verify key is set and OpenRouter API is reachable."""
        if not self.api_key:
            return False
        try:
            import httpx
            async with httpx.AsyncClient() as http:
                r = await http.get(
                    f"{OPENROUTER_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=8,
                )
                return r.status_code == 200
        except Exception as e:
            logger.error(f"OpenRouter health check failed: {str(e)}")
            return False
