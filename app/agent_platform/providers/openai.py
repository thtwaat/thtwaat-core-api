"""
app/agent_platform/providers/openai.py
OpenAI Provider — Real SDK Implementation for the Agent Platform.

Delegates to the shared app/ai/providers/openai.py (OpenAIProvider) so
that all SDK logic lives in one place and the Agent Platform gateway receives
a real UnifiedChatResponse.
"""
import logging
from typing import Dict, Any

from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry
from app.ai.providers.openai import OpenAIProvider as CoreOpenAIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    Agent Platform wrapper around the core OpenAIProvider.
    Receives a UnifiedChatRequest, calls the real OpenAI SDK,
    and returns a UnifiedChatResponse.
    """

    def __init__(self, api_key: str, base_url: str = None):
        super().__init__(api_key=api_key, base_url=base_url)
        # Instantiate the core provider and inject the resolved API key
        self._core = CoreOpenAIProvider()
        # Override with the key passed by the gateway (from settings/resolver)
        self._core.api_key = api_key
        # Reset lazily cached client so it picks up the overridden key
        self._core._client = None

    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        logger.info(
            f"OpenAIProvider (agent_platform): routing to real SDK "
            f"[model={request.model}, company={request.company_id}]"
        )

        kwargs: Dict[str, Any] = {
            "temperature": request.temperature,
        }
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens

        result = await self._core.chat(
            messages=request.messages,
            model=request.model,
            **kwargs,
        )

        return UnifiedChatResponse(
            content=result.content,
            provider="openai",
            model=result.model_used or request.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.input_tokens + result.output_tokens,
            finish_reason="stop",
        )


ProviderRegistry.register("openai", OpenAIProvider)
