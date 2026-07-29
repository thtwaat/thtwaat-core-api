"""
app/ai/providers/anthropic.py
Anthropic Claude Provider - Real SDK Implementation
"""
import logging
from typing import List, Dict, Any
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Fallback model priority list — newest Haiku is cheapest/fastest first
ANTHROPIC_FALLBACK_MODELS = [
    "claude-haiku-4-5",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
    "claude-3-5-sonnet-20241022",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
]


class AnthropicProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self._client = None

    def _get_client(self):
        """Lazily initialize the Anthropic async client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                if not self.api_key:
                    raise ValueError("ANTHROPIC_API_KEY is not configured in .env")
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "anthropic package is not installed. Run: pip install anthropic"
                )
        return self._client

    def _resolve_model(self, model: str) -> str:
        """Return model as-is; fallback to default if empty."""
        if not model:
            return ANTHROPIC_FALLBACK_MODELS[0]
        return model

    def _split_system_and_messages(
        self, messages: List[Dict[str, str]]
    ) -> tuple[str, List[Dict[str, str]]]:
        """
        Anthropic requires system prompt as a separate top-level parameter.
        Extract the first system message (if any) and return the rest.
        """
        system_prompt = ""
        chat_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content  # last system message wins
            else:
                chat_messages.append({"role": role, "content": content})
        return system_prompt, chat_messages

    async def chat(
        self, messages: List[Dict[str, str]], model: str, **kwargs
    ) -> AIProviderResponse:
        client = self._get_client()
        resolved_model = self._resolve_model(model)
        logger.info(f"Anthropic Provider: Generating chat using {resolved_model}")

        system_prompt, chat_messages = self._split_system_and_messages(messages)

        # Anthropic requires at least one user message
        if not chat_messages:
            chat_messages = [{"role": "user", "content": "Hello"}]

        async def _call(m: str) -> AIProviderResponse:
            params: Dict[str, Any] = {
                "model": m,
                "max_tokens": kwargs.get("max_tokens") or 1024,
                "messages": chat_messages,
            }
            if system_prompt:
                params["system"] = system_prompt
            if kwargs.get("temperature") is not None:
                params["temperature"] = kwargs["temperature"]

            response = await client.messages.create(**params)

            content = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens if response.usage else 0
            output_tokens = response.usage.output_tokens if response.usage else 0

            return AIProviderResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=response.model,
                provider_response_id=response.id,
            )

        try:
            return await _call(resolved_model)

        except Exception as e:
            logger.error(
                f"Anthropic chat error (model={resolved_model}): {str(e)}"
            )
            # Automatic fallback to next available model
            for fallback_model in ANTHROPIC_FALLBACK_MODELS:
                if fallback_model == resolved_model:
                    continue
                logger.info(f"Anthropic: Falling back to {fallback_model}")
                try:
                    return await _call(fallback_model)
                except Exception as fb_err:
                    logger.error(
                        f"Anthropic fallback {fallback_model} failed: {str(fb_err)}"
                    )
                    continue
            raise Exception(f"Anthropic Provider Error: {str(e)}")

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        """Single prompt generation via chat completions endpoint."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages=messages, model=model, **kwargs)

    async def models(self) -> List[str]:
        """Return a list of supported Claude models."""
        try:
            client = self._get_client()
            # SDK v0.x exposes models.list() — available from anthropic >= 0.26
            response = await client.models.list()
            model_ids = [m.id for m in response.data] if hasattr(response, "data") else []
            return model_ids or ANTHROPIC_FALLBACK_MODELS
        except Exception as e:
            logger.warning(
                f"Anthropic models list failed, using defaults: {str(e)}"
            )
            return ANTHROPIC_FALLBACK_MODELS

    async def health(self) -> bool:
        """Verify API key is set and can connect to Anthropic."""
        if not self.api_key:
            return False
        try:
            client = self._get_client()
            # Lightweight check — list models instead of sending a message
            await client.models.list()
            return True
        except Exception as e:
            logger.error(f"Anthropic health check failed: {str(e)}")
            return False
