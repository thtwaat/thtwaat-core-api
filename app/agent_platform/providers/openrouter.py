from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry

class OpenRouterProvider(LLMProvider):
    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        # Mock logic to simulate OpenRouter call
        return UnifiedChatResponse(
            content="This is a mocked response from OpenRouter.",
            provider=request.provider,
            model=request.model,
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            finish_reason="stop"
        )

ProviderRegistry.register("openrouter", OpenRouterProvider)
