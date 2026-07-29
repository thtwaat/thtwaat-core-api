"""
app/ai/providers/ollama.py
Ollama Provider Implementation
"""
import uuid
import logging
import httpx
import os
from typing import List, Dict, Any
from app.ai.providers.base import AIProvider, AIProviderResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OllamaProvider(AIProvider):
    def __init__(self):
        # Enforce host.docker.internal if running in Docker on Windows
        self.url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"[Ollama]: Generating chat using {model}")
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                
                content = data.get("message", {}).get("content", "")
                input_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", 0)
                
                return AIProviderResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_used=model,
                    provider_response_id=f"ollama-{uuid.uuid4().hex[:12]}"
                )
        except Exception as e:
            logger.error(f"Ollama chat error: {str(e)}")
            raise e

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"[Ollama]: Generating text using {model}")
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                
                content = data.get("response", "")
                input_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", 0)
                
                return AIProviderResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_used=model,
                    provider_response_id=f"ollama-{uuid.uuid4().hex[:12]}"
                )
        except Exception as e:
            logger.error(f"Ollama generate error: {str(e)}")
            raise e

    async def models(self) -> List[str]:
        return ["qwen2.5-coder:3b"]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
