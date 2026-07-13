"""
app/ai/providers/openai.py
OpenAI Provider Stub
"""
import uuid
import logging
from typing import List, Dict, Any
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OpenAIProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
    
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [OpenAI]: Generating chat using {model}")
        return AIProviderResponse(
            content=f"Stub response from OpenAI ({model})",
            input_tokens=15,
            output_tokens=30,
            model_used=model,
            provider_response_id=f"chatcmpl-{uuid.uuid4().hex[:12]}"
        )

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [OpenAI]: Generating text using {model}")
        return AIProviderResponse(
            content=f"Stub response from OpenAI ({model}) for prompt.",
            input_tokens=10,
            output_tokens=20,
            model_used=model,
            provider_response_id=f"cmpl-{uuid.uuid4().hex[:12]}"
        )

    async def models(self) -> List[str]:
        return ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]

    async def health(self) -> bool:
        return bool(self.api_key)
