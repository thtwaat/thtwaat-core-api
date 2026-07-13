"""
app/ai/providers/factory.py

Factory for resolving AI Providers.
"""
from app.ai.providers.base import AIProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openrouter import OpenRouterProvider

class AIProviderFactory:
    @staticmethod
    def get_provider(provider_name: str) -> AIProvider:
        provider_name = provider_name.lower()
        if provider_name == "openai":
            return OpenAIProvider()
        elif provider_name == "gemini":
            return GeminiProvider()
        elif provider_name == "anthropic" or provider_name == "claude":
            return AnthropicProvider()
        elif provider_name == "ollama":
            return OllamaProvider()
        elif provider_name == "openrouter":
            return OpenRouterProvider()
        else:
            raise ValueError(f"Unknown AI provider: {provider_name}")
