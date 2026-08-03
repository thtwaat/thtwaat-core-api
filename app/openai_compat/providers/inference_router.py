"""InferenceRouter — health-aware policy routing (Sem03 W1 D3)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException, status

from app.config.settings import settings
from app.openai_compat.inference_routing_repository import (
    InferenceRoutingRepository,
    ProviderProfile,
    get_routing_repository,
)
from app.openai_compat.providers.base import InferenceProvider, ProviderNotFoundError
from app.openai_compat.providers.capabilities import ProviderCapability
from app.openai_compat.providers.health_cache import (
    ProviderHealthCache,
    get_health_cache,
)
from app.openai_compat.providers.metrics import (
    InferenceRoutingMetrics,
    get_routing_metrics,
)
from app.openai_compat.providers.registry import (
    InferenceProviderRegistry,
    get_registry,
)


ROUTING_POLICIES = frozenset(
    {
        "default",
        "cheapest",
        "fastest",
        "highest_quality",
        "preferred_provider",
    }
)


@dataclass
class RoutingDecision:
    provider_name: str
    provider: InferenceProvider
    policy: str
    capability: str
    model: str
    routing_time_ms: float
    skipped_unhealthy: List[str] = field(default_factory=list)
    candidates: List[str] = field(default_factory=list)
    reason: str = ""


def _model_not_found(model_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "message": f"The model '{model_id}' does not exist",
                "type": "invalid_request_error",
                "code": "model_not_found",
            }
        },
    )


def _unknown_provider(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "message": f"Unknown or disabled provider '{name}'",
                "type": "invalid_request_error",
                "code": "unknown_provider",
            }
        },
    )


def _no_healthy_provider(model_id: str, skipped: Sequence[str]) -> HTTPException:
    skipped_s = ", ".join(skipped) if skipped else "(none)"
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "message": (
                    f"No healthy provider available for model '{model_id}' "
                    f"(skipped unhealthy: {skipped_s})"
                ),
                "type": "api_error",
                "code": "no_healthy_provider",
            }
        },
    )


class InferenceRouter:
    """
    Intelligent provider selection for THTWAAT Cloud.

    Day 3 scope: policies + health skip + capabilities + metrics.
    Not included: streaming, retries, circuit breaker, load balancing, parallel fan-out.
    """

    def __init__(
        self,
        *,
        registry: Optional[InferenceProviderRegistry] = None,
        repository: Optional[InferenceRoutingRepository] = None,
        health_cache: Optional[ProviderHealthCache] = None,
        metrics: Optional[InferenceRoutingMetrics] = None,
    ) -> None:
        self.registry = registry or get_registry()
        self.repository = repository or get_routing_repository()
        self.health_cache = health_cache or get_health_cache()
        self.metrics = metrics or get_routing_metrics()

    def active_policy(self, override: Optional[str] = None) -> str:
        raw = (override or getattr(settings, "INFERENCE_ROUTING_POLICY", None) or "default")
        policy = str(raw).strip().lower() or "default"
        if policy not in ROUTING_POLICIES:
            return "default"
        return policy

    def default_provider(self) -> str:
        return (getattr(settings, "INFERENCE_DEFAULT_PROVIDER", None) or "ollama").strip().lower()

    def fallback_provider(self) -> Optional[str]:
        raw = getattr(settings, "INFERENCE_FALLBACK_PROVIDER", None)
        if raw is None or str(raw).strip() == "":
            return None
        return str(raw).strip().lower()

    def sync_health_ttl(self) -> None:
        ttl = float(getattr(settings, "INFERENCE_HEALTH_CACHE_TTL_SECONDS", 30) or 30)
        self.health_cache.set_ttl(ttl)

    async def is_healthy(self, provider: InferenceProvider) -> bool:
        self.sync_health_ttl()

        async def _probe() -> Dict[str, Any]:
            try:
                return await provider.health()
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": str(exc)}

        result = await self.health_cache.get_or_probe(provider.name, _probe)
        return bool(result.get("ok"))

    def _owners_of_model(self, model_id: str) -> List[str]:
        owners: List[str] = []
        for prov in self.registry.enabled_providers():
            for item in prov.models():
                if item.get("id") == model_id:
                    owners.append(prov.name)
                    break
        return owners

    def _rank(
        self,
        names: Sequence[str],
        *,
        policy: str,
        preferred: Optional[str],
    ) -> List[str]:
        profiles: Dict[str, ProviderProfile] = {}
        for name in names:
            profile = self.repository.get_profile(name)
            if profile is None:
                # Unknown profile — lowest priority / mid scores
                profiles[name] = ProviderProfile(
                    name=name,
                    priority=0,
                    cost=50.0,
                    latency_ms=500.0,
                    quality=50.0,
                    capabilities=frozenset({ProviderCapability.CHAT}),
                )
            else:
                profiles[name] = profile

        ordered = list(names)
        if policy == "cheapest":
            ordered.sort(key=lambda n: (profiles[n].cost, -profiles[n].priority, n))
        elif policy == "fastest":
            ordered.sort(key=lambda n: (profiles[n].latency_ms, -profiles[n].priority, n))
        elif policy == "highest_quality":
            ordered.sort(key=lambda n: (-profiles[n].quality, -profiles[n].priority, n))
        elif policy in {"default", "preferred_provider"}:
            pref = (preferred or self.default_provider()).strip().lower()
            priority_index = {name: i for i, name in enumerate(self.repository.priority_order())}

            def _key(n: str) -> tuple:
                return (
                    0 if n == pref else 1,
                    priority_index.get(n, 10_000),
                    -profiles[n].priority,
                    n,
                )

            ordered.sort(key=_key)
        else:
            ordered.sort(key=lambda n: (-profiles[n].priority, n))
        return ordered

    async def route(
        self,
        *,
        model: str,
        provider: Optional[str] = None,
        capability: str | ProviderCapability = ProviderCapability.CHAT,
        policy: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Select a healthy provider for model + capability under the active policy.

        Explicit `provider=` still validated; if that instance is unhealthy the
        router skips it and may use INFERENCE_FALLBACK_PROVIDER / other healthy owners.
        """
        started = time.perf_counter()
        from app.openai_compat.providers import ensure_providers_registered

        ensure_providers_registered()
        self.sync_health_ttl()

        model_id = (model or "").strip()
        if not model_id:
            raise _model_not_found(model_id)

        cap = (
            capability
            if isinstance(capability, ProviderCapability)
            else ProviderCapability(str(capability).strip().lower())
        )
        active_policy = self.active_policy(policy)
        skipped: List[str] = []
        explicit = (provider or "").strip().lower() or None

        # Explicit unknown/disabled → 400 (Day 2 contract)
        if explicit is not None:
            try:
                self.registry.get(explicit, require_enabled=True)
            except ProviderNotFoundError as exc:
                raise _unknown_provider(explicit) from exc

        owners = self._owners_of_model(model_id)
        if not owners:
            raise _model_not_found(model_id)

        # Capability filter on owners
        capable_owners = [
            name
            for name in owners
            if self.repository.supports(name, cap)
        ]
        if not capable_owners:
            raise _model_not_found(model_id)

        if explicit is not None and explicit not in capable_owners:
            # Provider enabled but does not list this model
            raise _model_not_found(model_id)

        candidate_pool: List[str] = [explicit] if explicit else list(capable_owners)

        # Always allow fallback provider into the pool when configured and capable
        fb = self.fallback_provider()
        if fb and fb in capable_owners and fb not in candidate_pool:
            candidate_pool.append(fb)
        # When explicit is unhealthy, also consider other capable owners (health-aware skip)
        if explicit is not None:
            for name in capable_owners:
                if name not in candidate_pool:
                    candidate_pool.append(name)

        healthy: List[str] = []
        for name in candidate_pool:
            try:
                inst = self.registry.get(name, require_enabled=True)
            except ProviderNotFoundError:
                continue
            if await self.is_healthy(inst):
                healthy.append(name)
            else:
                skipped.append(name)

        if not healthy:
            raise _no_healthy_provider(model_id, skipped)

        preferred = explicit or self.default_provider()
        ranked = self._rank(healthy, policy=active_policy, preferred=preferred)
        chosen = ranked[0]
        inst = self.registry.get(chosen, require_enabled=True)
        routing_ms = (time.perf_counter() - started) * 1000.0
        self.metrics.record_selection(chosen, policy=active_policy, routing_time_ms=routing_ms)

        reason = f"policy={active_policy}"
        if skipped:
            reason += f"; skipped_unhealthy={skipped}"
        if chosen == fb and explicit and explicit in skipped:
            reason += f"; fallback={fb}"

        return RoutingDecision(
            provider_name=chosen,
            provider=inst,
            policy=active_policy,
            capability=cap.value,
            model=model_id,
            routing_time_ms=routing_ms,
            skipped_unhealthy=skipped,
            candidates=ranked,
            reason=reason,
        )
