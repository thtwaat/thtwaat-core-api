from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.registries.provider_registry import ProviderRegistry

class OllamaProvider(LLMProvider):
    async def generate_response(self, request: UnifiedChatRequest) -> UnifiedChatResponse:
        # Mock logic to simulate Ollama local call
        return UnifiedChatResponse(
            content="This is a mocked response from local Ollama.",
            provider=request.provider,
            model=request.model,
            input_tokens=50,
            output_tokens=5,
            total_tokens=55,
            finish_reason="stop"
        )

ProviderRegistry.register("ollama", OllamaProvider)
