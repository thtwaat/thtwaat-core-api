"""Inference routing service (Sem03 W1 D3) — service layer over InferenceRouter."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Union

from app.openai_compat.inference_routing_repository import (
    InferenceRoutingRepository,
    get_routing_repository,
)
from app.openai_compat.providers.capabilities import ProviderCapability
from app.openai_compat.providers.health_cache import get_health_cache
from app.openai_compat.providers.inference_router import (
    InferenceRouter,
    RoutingDecision,
)
from app.openai_compat.providers.metrics import get_routing_metrics
from app.openai_compat.providers.registry import get_registry


class InferenceRoutingService:
    """
    Service facade used by CompletionsService.

    Keeps FastAPI routers free of routing policy / health-cache logic.
    """

    def __init__(
        self,
        *,
        router: Optional[InferenceRouter] = None,
        repository: Optional[InferenceRoutingRepository] = None,
    ) -> None:
        self.repository = repository or get_routing_repository()
        self.router = router or InferenceRouter(
            registry=get_registry(),
            repository=self.repository,
            health_cache=get_health_cache(),
            metrics=get_routing_metrics(),
        )

    async def select_provider(
        self,
        *,
        model: str,
        provider: Optional[str] = None,
        capability: str | ProviderCapability = ProviderCapability.CHAT,
        policy: Optional[str] = None,
    ) -> RoutingDecision:
        return await self.router.route(
            model=model,
            provider=provider,
            capability=capability,
            policy=policy,
        )

    async def chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        provider: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        policy: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[Dict[str, Any], RoutingDecision]:
        """Route then invoke provider.chat(); records latency / errors metrics."""
        decision = await self.select_provider(
            model=model,
            provider=provider,
            capability=ProviderCapability.CHAT,
            policy=policy,
        )
        started = time.perf_counter()
        try:
            result = await decision.provider.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception:
            self.router.metrics.record_error(decision.provider_name)
            raise
        latency_ms = (time.perf_counter() - started) * 1000.0
        self.router.metrics.record_latency(decision.provider_name, latency_ms)
        return result, decision

    async def embeddings(
        self,
        *,
        model: str,
        input: Union[str, List[str]],
        provider: Optional[str] = None,
        policy: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[Dict[str, Any], RoutingDecision]:
        decision = await self.select_provider(
            model=model,
            provider=provider,
            capability=ProviderCapability.EMBEDDINGS,
            policy=policy,
        )
        started = time.perf_counter()
        try:
            result = await decision.provider.embeddings(
                model=model, input=input, **kwargs
            )
        except Exception:
            self.router.metrics.record_error(decision.provider_name)
            raise
        latency_ms = (time.perf_counter() - started) * 1000.0
        self.router.metrics.record_latency(decision.provider_name, latency_ms)
        return result, decision

    def metrics_snapshot(self) -> Dict[str, Any]:
        return self.router.metrics.snapshot()

    def capabilities_map(self) -> Dict[str, List[str]]:
        return {
            p.name: p.capability_names() for p in self.repository.list_profiles()
        }


def get_inference_routing_service() -> InferenceRoutingService:
    return InferenceRoutingService()
