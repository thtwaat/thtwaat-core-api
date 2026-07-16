import uuid
from typing import Optional

class Resolvers:
    """
    Mock resolvers that fetch configuration from the database.
    Since we are not fully wiring the DB connection here, these act as stubs
    that would normally query `ProviderConfig`, `ModelConfig`, and `AgentConfig`.
    """
    
    @staticmethod
    def get_company_config(company_id: str) -> dict:
        """Validates tenant existence and limits."""
        return {"company_id": company_id, "is_active": True}

    @staticmethod
    def get_provider_config(company_id: str, provider_name: str) -> dict:
        """Fetches API keys and base URLs for a provider."""
        # Mock logic
        return {
            "provider_name": provider_name,
            "api_key_secret": f"mock_{provider_name}_key",
            "base_url": None
        }
        
    @staticmethod
    def get_model_config(company_id: str, provider_name: str, model_name: str) -> dict:
        """Fetches model pricing and context windows."""
        # Mock logic
        return {
            "model_name": model_name,
            "cost_per_1k_prompt": 0.01,
            "cost_per_1k_completion": 0.03
        }
