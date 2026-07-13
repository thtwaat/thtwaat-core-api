"""
app/ai/providers/ollama.py
Ollama Provider Stub
"""
import uuid
import logging
from typing import List, Dict, Any
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OllamaProvider(AIProvider):
    def __init__(self):
        self.url = settings.OLLAMA_URL
    
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [Ollama]: Generating chat using {model}")
        return AIProviderResponse(
            content=f"Stub response from Ollama ({model})",
            input_tokens=5,
            output_tokens=10,
            model_used=model,
            provider_response_id=f"ollama-{uuid.uuid4().hex[:12]}"
        )

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"STUB [Ollama]: Generating text using {model}")
        return AIProviderResponse(
            content=f"Stub response from Ollama ({model}) for prompt.",
            input_tokens=5,
            output_tokens=10,
            model_used=model,
            provider_response_id=f"ollama-{uuid.uuid4().hex[:12]}"
        )

    async def models(self) -> List[str]:
        return ["llama3", "mistral", "gemma"]

    async def health(self) -> bool:
        return bool(self.url)
