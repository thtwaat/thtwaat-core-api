"""
app/ai/providers/gemini.py
Google Gemini Provider Implementation
"""
import uuid
import logging
import warnings
from typing import List, Dict, Any
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from google.api_core import exceptions
from app.ai.providers.base import AIProvider, AIProviderResponse

from app.config.settings import settings

logger = logging.getLogger(__name__)

class GeminiProvider(AIProvider):
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
    
    def _handle_api_error(self, e: Exception, operation: str) -> None:
        """Handle common Gemini API errors and log them."""
        logger.error(f"Gemini API {operation} Error: {str(e)}")
        if isinstance(e, exceptions.ResourceExhausted):
            raise Exception("Gemini API Rate Limit Exceeded")
        elif isinstance(e, exceptions.InvalidArgument):
            raise Exception("Invalid arguments provided to Gemini API")
        elif isinstance(e, exceptions.DeadlineExceeded):
            raise Exception("Gemini API Timeout")
        elif isinstance(e, exceptions.PermissionDenied):
            raise Exception("Gemini API Permission Denied (Invalid Key?)")
        else:
            raise Exception(f"Gemini API Error: {str(e)}")

    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"Gemini Provider: Generating chat using {model}")
        try:
            gemini_model = genai.GenerativeModel(model)
            # Map standard role to Gemini roles ('user' -> 'user', 'assistant' -> 'model')
            formatted_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                formatted_messages.append({"role": role, "parts": [msg["content"]]})
                
            response = gemini_model.generate_content(formatted_messages)
            
            # Extract tokens
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count if usage else 0
            output_tokens = usage.candidates_token_count if usage else 0
            
            return AIProviderResponse(
                content=response.text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=model,
                provider_response_id=f"gemini-{uuid.uuid4().hex[:12]}"
            )
        except Exception as e:
            self._handle_api_error(e, "chat")

    async def generate(self, prompt: str, model: str, **kwargs) -> AIProviderResponse:
        logger.info(f"Gemini Provider: Generating text using {model}")
        try:
            gemini_model = genai.GenerativeModel(model)
            response = gemini_model.generate_content(prompt)
            
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count if usage else 0
            output_tokens = usage.candidates_token_count if usage else 0
            
            return AIProviderResponse(
                content=response.text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=model,
                provider_response_id=f"gemini-{uuid.uuid4().hex[:12]}"
            )
        except Exception as e:
            self._handle_api_error(e, "generate")

    async def models(self) -> List[str]:
        return ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]

    async def health(self) -> bool:
        if not self.api_key:
            return False
        try:
            # Check models endpoint as a lightweight health check
            # Next iteration can just be genai.list_models()
            models = list(genai.list_models())
            return len(models) > 0
        except Exception as e:
            logger.error(f"Gemini Health Check Failed: {str(e)}")
            return False
