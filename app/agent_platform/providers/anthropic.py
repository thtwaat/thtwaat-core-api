from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry

class AnthropicProvider(LLMProvider):
    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        # Mock logic to simulate Anthropic Claude call
        return UnifiedChatResponse(
            content="This is a mocked response from Anthropic.",
            provider=request.provider,
            model=request.model,
            input_tokens=18,
            output_tokens=15,
            total_tokens=33,
            finish_reason="end_turn"
        )

ProviderRegistry.register("anthropic", AnthropicProvider)
