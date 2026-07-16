from typing import Dict, Type
from app.agent_platform.providers.base import LLMProvider

class ProviderRegistry:
    """
    Registry for loading and instantiating LLM Providers dynamically.
    """
    
    _providers: Dict[str, Type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[LLMProvider]):
        """Registers a provider class under a specific name."""
        cls._providers[name] = provider_class

    @classmethod
    def get_provider(cls, name: str, api_key: str, base_url: str = None) -> LLMProvider:
        """
        Instantiates a provider by name.
        """
        provider_class = cls._providers.get(name)
        if not provider_class:
            raise ValueError(f"Provider '{name}' is not registered.")
        return provider_class(api_key=api_key, base_url=base_url)
