"""Static provider routing profiles (Sem03 W1 D3) — repository layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from app.config.settings import settings
from app.openai_compat.providers.capabilities import ProviderCapability


@dataclass(frozen=True)
class ProviderProfile:
    """Relative scoring used by routing policies (not live measurements)."""

    name: str
    priority: int
    cost: float
    latency_ms: float
    quality: float
    capabilities: frozenset[ProviderCapability] = field(default_factory=frozenset)

    def capability_names(self) -> List[str]:
        return sorted(c.value for c in self.capabilities)


# Higher priority = preferred under `default` / `preferred_provider` tie-breaks.
# cost: higher = more expensive; latency_ms: higher = slower; quality: higher = better.
_DEFAULT_PROFILES: Dict[str, ProviderProfile] = {
    "ollama": ProviderProfile(
        name="ollama",
        priority=100,
        cost=0.0,
        latency_ms=900.0,
        quality=65.0,
        capabilities=frozenset(
            {ProviderCapability.CHAT, ProviderCapability.EMBEDDINGS}
        ),
    ),
    "vllm": ProviderProfile(
        name="vllm",
        priority=80,
        cost=5.0,
        latency_ms=150.0,
        quality=75.0,
        capabilities=frozenset(
            {ProviderCapability.CHAT, ProviderCapability.EMBEDDINGS}
        ),
    ),
    "openai": ProviderProfile(
        name="openai",
        priority=60,
        cost=70.0,
        latency_ms=300.0,
        quality=95.0,
        capabilities=frozenset(
            {
                ProviderCapability.CHAT,
                ProviderCapability.EMBEDDINGS,
                ProviderCapability.IMAGE_GENERATION,
                ProviderCapability.SPEECH_TO_TEXT,
                ProviderCapability.TEXT_TO_SPEECH,
            }
        ),
    ),
    "gemini": ProviderProfile(
        name="gemini",
        priority=50,
        cost=40.0,
        latency_ms=350.0,
        quality=88.0,
        capabilities=frozenset(
            {
                ProviderCapability.CHAT,
                ProviderCapability.EMBEDDINGS,
                ProviderCapability.IMAGE_GENERATION,
            }
        ),
    ),
    "anthropic": ProviderProfile(
        name="anthropic",
        priority=40,
        cost=80.0,
        latency_ms=400.0,
        quality=98.0,
        capabilities=frozenset({ProviderCapability.CHAT}),
    ),
}


class InferenceRoutingRepository:
    """
    Repository for provider routing metadata (priority / cost / latency / quality / caps).

    No DB table on Day 3 — profiles are code + optional env priority override.
    """

    def __init__(self, profiles: Optional[Dict[str, ProviderProfile]] = None) -> None:
        self._profiles: Dict[str, ProviderProfile] = dict(profiles or _DEFAULT_PROFILES)

    def list_profiles(self) -> List[ProviderProfile]:
        return [self._profiles[k] for k in sorted(self._profiles.keys())]

    def get_profile(self, name: str) -> Optional[ProviderProfile]:
        return self._profiles.get((name or "").strip().lower())

    def upsert_profile(self, profile: ProviderProfile) -> None:
        self._profiles[profile.name.strip().lower()] = profile

    def capabilities_for(self, name: str) -> Set[ProviderCapability]:
        profile = self.get_profile(name)
        if profile is None:
            return set()
        return set(profile.capabilities)

    def supports(self, name: str, capability: str | ProviderCapability) -> bool:
        caps = self.capabilities_for(name)
        need = (
            capability
            if isinstance(capability, ProviderCapability)
            else ProviderCapability(str(capability).strip().lower())
        )
        return need in caps

    def priority_order(self) -> List[str]:
        """
        Provider names ordered by priority desc.

        Optional override: INFERENCE_PROVIDER_PRIORITY=ollama,vllm,openai,...
        """
        raw = (getattr(settings, "INFERENCE_PROVIDER_PRIORITY", None) or "").strip()
        if raw:
            seen: List[str] = []
            for part in raw.split(","):
                key = part.strip().lower()
                if key and key not in seen:
                    seen.append(key)
            # Append any known profiles not listed
            for name in sorted(self._profiles.keys(), key=lambda n: -self._profiles[n].priority):
                if name not in seen:
                    seen.append(name)
            return seen
        return [
            p.name
            for p in sorted(self._profiles.values(), key=lambda p: (-p.priority, p.name))
        ]

    def providers_with_capability(
        self, capability: str | ProviderCapability, names: Sequence[str]
    ) -> List[str]:
        return [n for n in names if self.supports(n, capability)]


_REPO = InferenceRoutingRepository()


def get_routing_repository() -> InferenceRoutingRepository:
    return _REPO


def reset_routing_repository_for_tests() -> InferenceRoutingRepository:
    global _REPO
    _REPO = InferenceRoutingRepository()
    return _REPO
