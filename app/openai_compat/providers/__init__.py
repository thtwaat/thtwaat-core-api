"""Sem03 inference providers — OpenAI-compatible /v1 routing surface."""
from __future__ import annotations

from app.openai_compat.providers.base import (
    InferenceProvider,
    InferenceProviderError,
    ProviderConfigError,
    ProviderNotFoundError,
    ProviderTimeoutError,
    ProviderUpstreamError,
)
from app.openai_compat.providers.capabilities import ProviderCapability
from app.openai_compat.providers.registry import InferenceProviderRegistry, get_registry
from app.openai_compat.providers.routing import (
    resolve_provider_for_request,
    resolve_provider_name,
)

__all__ = [
    "InferenceProvider",
    "InferenceProviderError",
    "ProviderConfigError",
    "ProviderNotFoundError",
    "ProviderTimeoutError",
    "ProviderUpstreamError",
    "ProviderCapability",
    "InferenceProviderRegistry",
    "InferenceRouter",
    "RoutingDecision",
    "get_registry",
    "resolve_provider_for_request",
    "resolve_provider_name",
    "ensure_providers_registered",
]


def __getattr__(name: str):
    # Lazy export — avoids circular import with inference_routing_repository
    if name == "InferenceRouter":
        from app.openai_compat.providers.inference_router import InferenceRouter

        return InferenceRouter
    if name == "RoutingDecision":
        from app.openai_compat.providers.inference_router import RoutingDecision

        return RoutingDecision
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def ensure_providers_registered() -> InferenceProviderRegistry:
    """Register all Sem03 providers (idempotent; safe after test resets)."""
    from app.openai_compat.providers.anthropic import AnthropicInferenceProvider
    from app.openai_compat.providers.gemini import GeminiInferenceProvider
    from app.openai_compat.providers.ollama import OllamaInferenceProvider
    from app.openai_compat.providers.openai_provider import OpenAIInferenceProvider
    from app.openai_compat.providers.openrouter import OpenRouterInferenceProvider
    from app.openai_compat.providers.vllm import VllmInferenceProvider

    registry = get_registry()
    registry.register("ollama", OllamaInferenceProvider)
    registry.register("openai", OpenAIInferenceProvider)
    registry.register("gemini", GeminiInferenceProvider)
    registry.register("anthropic", AnthropicInferenceProvider)
    registry.register("openrouter", OpenRouterInferenceProvider)
    registry.register("vllm", VllmInferenceProvider)
    return registry
