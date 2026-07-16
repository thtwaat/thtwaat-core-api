from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry

class GeminiProvider(LLMProvider):
    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        # Mock logic to simulate Google Gemini call
        return UnifiedChatResponse(
            content="This is a mocked response from Gemini.",
            provider=request.provider,
            model=request.model,
            input_tokens=20,
            output_tokens=12,
            total_tokens=32,
            finish_reason="stop"
        )

ProviderRegistry.register("gemini", GeminiProvider)
