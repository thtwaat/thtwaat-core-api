from app.config.settings import settings


class Resolvers:
    """
    Fetches configuration needed by the AI Gateway.
    Provider-specific API keys are read from application settings.
    """

    @staticmethod
    def get_company_config(company_id: str) -> dict:
        """Validates tenant existence and limits."""
        # Company validation is enforced at the JWT authentication layer.
        # Future: query Company model from DB here.
        return {"company_id": company_id, "is_active": True}

    @staticmethod
    def get_provider_config(company_id: str, provider_name: str) -> dict:
        """Returns the API key and base URL for the requested provider."""
        provider_key_map = {
            "gemini": settings.GEMINI_API_KEY,
            "openai": settings.OPENAI_API_KEY,
            "anthropic": settings.ANTHROPIC_API_KEY,
            "openrouter": settings.OPENROUTER_API_KEY,
            "ollama": None,  # Ollama is local, no key needed
        }

        api_key = provider_key_map.get(provider_name)

        base_url_map = {
            "ollama": settings.OLLAMA_URL,
        }
        base_url = base_url_map.get(provider_name)

        return {
            "provider_name": provider_name,
            "api_key_secret": api_key,
            "base_url": base_url,
        }

    @staticmethod
    def get_model_config(company_id: str, provider_name: str, model_name: str) -> dict:
        """Returns pricing info for cost tracking. Defaults to 0 if unknown."""
        # Gemini Flash pricing as of 2025 (per 1k tokens)
        pricing = {
            "gemini": {"cost_per_1k_prompt": 0.00015, "cost_per_1k_completion": 0.0006},
            "openai": {"cost_per_1k_prompt": 0.005, "cost_per_1k_completion": 0.015},
            "anthropic": {"cost_per_1k_prompt": 0.008, "cost_per_1k_completion": 0.024},
            "openrouter": {"cost_per_1k_prompt": 0.001, "cost_per_1k_completion": 0.001},
            "ollama": {"cost_per_1k_prompt": 0.0, "cost_per_1k_completion": 0.0},
        }
        provider_pricing = pricing.get(provider_name, {"cost_per_1k_prompt": 0.0, "cost_per_1k_completion": 0.0})
        return {
            "model_name": model_name,
            **provider_pricing,
        }
