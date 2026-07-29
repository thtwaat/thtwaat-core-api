"""
app/agent_platform/providers/anthropic.py
Anthropic Claude Provider — Real SDK Implementation for the Agent Platform.

Delegates to the shared app/ai/providers/anthropic.py (AnthropicProvider) so
that all SDK logic lives in one place and the Agent Platform gateway receives
a real UnifiedChatResponse.
"""
import logging
from typing import List, Dict, Any

from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry
from app.ai.providers.anthropic import AnthropicProvider as CoreAnthropicProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """
    Agent Platform wrapper around the core AnthropicProvider.
    Receives a UnifiedChatRequest, calls the real Anthropic SDK,
    and returns a UnifiedChatResponse.
    """

    def __init__(self, api_key: str, base_url: str = None):
        super().__init__(api_key=api_key, base_url=base_url)
        # Instantiate the core provider and inject the resolved API key
        self._core = CoreAnthropicProvider()
        # Override with the key passed by the gateway (from settings/resolver)
        self._core.api_key = api_key
        # Reset lazily cached client so it picks up the overridden key
        self._core._client = None

    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        logger.info(
            f"AnthropicProvider (agent_platform): routing to real SDK "
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
            provider="anthropic",
            model=result.model_used or request.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.input_tokens + result.output_tokens,
            finish_reason="end_turn",
        )


ProviderRegistry.register("anthropic", AnthropicProvider)
