"""
app/ai/providers/openai.py
OpenAI Provider - Real SDK Implementation
"""
import uuid
import logging
from typing import List, Dict, Any, Optional
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Default fallback models in priority order
OPENAI_FALLBACK_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]

class OpenAIProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self._client = None

    def _get_client(self):
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                if not self.api_key:
                    raise ValueError("OPENAI_API_KEY is not configured in .env")
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("openai package is not installed. Run: pip install openai")
        return self._client

    def _resolve_model(self, model: str) -> str:
        """
        If a configured model is unavailable, automatically fall back
        to the first available fallback model.
        """
        if not model:
            return OPENAI_FALLBACK_MODELS[0]
        return model

    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        client = self._get_client()
        resolved_model = self._resolve_model(model)
        logger.info(f"OpenAI Provider: Generating chat using {resolved_model}")

        try:
            params: Dict[str, Any] = {
                "model": resolved_model,
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

            return AIProviderResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=response.model,
                provider_response_id=response.id
            )

        except Exception as e:
            logger.error(f"OpenAI chat error (model={resolved_model}): {str(e)}")
            # Try fallback models
            for fallback_model in OPENAI_FALLBACK_MODELS:
                if fallback_model == resolved_model:
                    continue
                logger.info(f"OpenAI: Falling back to {fallback_model}")
                try:
                    params["model"] = fallback_model
                    response = await client.chat.completions.create(**params)
                    content = response.choices[0].message.content or ""
                    usage = response.usage
                    return AIProviderResponse(
                        content=content,
                        input_tokens=usage.prompt_tokens if usage else 0,
                        output_tokens=usage.completion_tokens if usage else 0,
                        model_used=response.model,
                        provider_response_id=response.id
                    )
                except Exception as fb_err:
                    logger.error(f"OpenAI fallback {fallback_model} failed: {str(fb_err)}")
                    continue
            raise Exception(f"OpenAI Provider Error: {str(e)}")

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        """Single prompt generation via chat completions endpoint."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages=messages, model=model, **kwargs)

    async def models(self) -> List[str]:
        """Fetch live model list from OpenAI, fallback to defaults."""
        try:
            client = self._get_client()
            response = await client.models.list()
            chat_models = [
                m.id for m in response.data
                if "gpt" in m.id
            ]
            return sorted(chat_models) or OPENAI_FALLBACK_MODELS
        except Exception as e:
            logger.warning(f"OpenAI models list failed, using defaults: {str(e)}")
            return OPENAI_FALLBACK_MODELS

    async def health(self) -> bool:
        """Verify API key is set and can connect to OpenAI."""
        if not self.api_key:
            return False
        try:
            client = self._get_client()
            response = await client.models.list()
            return len(list(response.data)) > 0
        except Exception as e:
            logger.error(f"OpenAI health check failed: {str(e)}")
            return False
