from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry

class OpenAIProvider(LLMProvider):
    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        # Mock logic to simulate OpenAI call
        return UnifiedChatResponse(
            content="This is a mocked response from OpenAI.",
            provider=request.provider,
            model=request.model,
            input_tokens=15,
            output_tokens=10,
            total_tokens=25,
            finish_reason="stop"
        )

ProviderRegistry.register("openai", OpenAIProvider)
