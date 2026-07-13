"""
app/ai/providers/gemini.py
Google Gemini Provider Stub
"""
import uuid
import logging
from typing import List, Dict, Any
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

class GeminiProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
    
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [Gemini]: Generating chat using {model}")
        return AIProviderResponse(
            content=f"Stub response from Gemini ({model})",
            input_tokens=20,
            output_tokens=40,
            model_used=model,
            provider_response_id=f"gemini-{uuid.uuid4().hex[:12]}"
        )

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [Gemini]: Generating text using {model}")
        return AIProviderResponse(
            content=f"Stub response from Gemini ({model}) for prompt.",
            input_tokens=15,
            output_tokens=25,
            model_used=model,
            provider_response_id=f"gemini-{uuid.uuid4().hex[:12]}"
        )

    async def models(self) -> List[str]:
        return ["gemini-1.5-pro", "gemini-1.5-flash"]

    async def health(self) -> bool:
        return bool(self.api_key)
