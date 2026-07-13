"""
app/ai/providers/openrouter.py
OpenRouter Provider Stub
"""
import uuid
import logging
from typing import List, Dict, Any
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OpenRouterProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
    
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [OpenRouter]: Generating chat using {model}")
        return AIProviderResponse(
            content=f"Stub response from OpenRouter ({model})",
            input_tokens=30,
            output_tokens=60,
            model_used=model,
            provider_response_id=f"or-{uuid.uuid4().hex[:12]}"
        )

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [OpenRouter]: Generating text using {model}")
        return AIProviderResponse(
            content=f"Stub response from OpenRouter ({model}) for prompt.",
            input_tokens=25,
            output_tokens=50,
            model_used=model,
            provider_response_id=f"or-{uuid.uuid4().hex[:12]}"
        )

    async def models(self) -> List[str]:
        return ["meta-llama/llama-3-70b-instruct", "anthropic/claude-3-opus", "google/gemini-pro"]

    async def health(self) -> bool:
        return bool(self.api_key)
