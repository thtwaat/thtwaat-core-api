from app.agent_platform.providers.base import LLMProvider
from app.agent_platform.registries.provider_registry import ProviderRegistry

class ProviderFactory:
    """
    Instantiates the correct provider using the registry.
    """
    
    @staticmethod
    def get_provider(provider_name: str, config: dict) -> LLMProvider:
        """
        Creates an instance of the provider with the decrypted API key.
        """
        api_key = config.get("api_key_secret")
        base_url = config.get("base_url")
        return ProviderRegistry.get_provider(provider_name, api_key, base_url)
