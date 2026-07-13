"""
app/ai/providers/anthropic.py
Anthropic Claude Provider Stub
"""
import uuid
import logging
from typing import List, Dict, Any
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

class AnthropicProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
    
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [Anthropic]: Generating chat using {model}")
        return AIProviderResponse(
            content=f"Stub response from Claude ({model})",
            input_tokens=25,
            output_tokens=50,
            model_used=model,
            provider_response_id=f"msg_{uuid.uuid4().hex[:12]}"
        )

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [Anthropic]: Generating text using {model}")
        return AIProviderResponse(
            content=f"Stub response from Claude ({model}) for prompt.",
            input_tokens=20,
            output_tokens=40,
            model_used=model,
            provider_response_id=f"msg_{uuid.uuid4().hex[:12]}"
        )

    async def models(self) -> List[str]:
        return ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]

    async def health(self) -> bool:
        return bool(self.api_key)
