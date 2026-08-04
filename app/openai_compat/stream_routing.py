"""Stream provider routing — health-aware + policy-ranked (Sem03 W2 D3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from app.config.settings import settings
from app.openai_compat.errors import no_healthy_provider, openai_error
from app.openai_compat.providers.base import ProviderNotFoundError

STREAM_PROVIDER_POLICIES = frozenset(
    {"auto", "ollama", "openai", "gemini", "anthropic"}
)

STREAM_PROVIDER_NAMES = frozenset({"ollama", "openai", "gemini", "anthropic"})


@dataclass
class StreamProviderChain:
    """Ordered stream attempt list plus health-skip metadata."""

    providers: List[str]
    skipped_unhealthy: List[str] = field(default_factory=list)


def stream_fallback_order() -> List[str]:
    raw = getattr(settings, "STREAM_FALLBACK_ORDER", None) or "ollama,openai,gemini,anthropic"
    out: List[str] = []
    for part in str(raw).split(","):
        name = part.strip().lower()
        if name and name in STREAM_PROVIDER_NAMES and name not in out:
            out.append(name)
    return out or ["ollama", "openai", "gemini", "anthropic"]


def normalize_stream_provider(provider: Optional[str]) -> str:
    """Request provider → policy name. Empty/None → auto (default)."""
    default = (getattr(settings, "STREAM_DEFAULT_PROVIDER", None) or "auto").strip().lower()
    if default not in STREAM_PROVIDER_POLICIES:
        default = "auto"
    if provider is None or str(provider).strip() == "":
        return default
    name = str(provider).strip().lower()
    if name not in STREAM_PROVIDER_POLICIES:
        raise openai_error(
            status_code=400,
            message=(
                f"Unknown stream provider '{provider}'. "
                f"Use one of: {', '.join(sorted(STREAM_PROVIDER_POLICIES))}."
            ),
            type_="invalid_request_error",
            code="unknown_provider",
            param="provider",
        )
    return name


async def filter_healthy_stream_providers(
    names: Sequence[str],
    *,
    router: Optional[object] = None,
) -> Tuple[List[str], List[str]]:
    """
    Keep healthy stream providers; return (healthy_ordered, skipped_unhealthy).

    Uses InferenceRouter.is_healthy + shared ProviderHealthCache (TTL cooldown).
    """
    from app.openai_compat.providers import ensure_providers_registered
    from app.openai_compat.providers.inference_router import InferenceRouter

    ensure_providers_registered()
    rtr = router if router is not None else InferenceRouter()
    rtr.sync_health_ttl()

    healthy: List[str] = []
    skipped: List[str] = []
    for raw in names:
        name = (raw or "").strip().lower()
        if not name or name not in STREAM_PROVIDER_NAMES:
            continue
        try:
            inst = rtr.registry.get(name, require_enabled=True)
        except ProviderNotFoundError:
            skipped.append(name)
            continue
        if await rtr.is_healthy(inst):
            healthy.append(name)
        else:
            skipped.append(name)
    return healthy, skipped


def _stream_pool_for_model(model: str, router: object) -> List[str]:
    """Owners ∩ stream providers, or full STREAM_FALLBACK_ORDER if unknown."""
    order = stream_fallback_order()
    owners = [
        n
        for n in router._owners_of_model((model or "").strip())  # type: ignore[attr-defined]
        if n in STREAM_PROVIDER_NAMES
    ]
    if owners:
        return _dedupe([*owners, *order])
    return list(order)


async def resolve_stream_provider_chain(
    *,
    model: str,
    provider: Optional[str],
) -> StreamProviderChain:
    """
    Build ordered healthy provider attempt list for a stream request.

    - provider=auto → policy-ranked stream pool, then health-filter
    - provider=<name> → that name first even if unhealthy (override);
      remaining fallbacks health-filtered
    Fallback is only used by StreamEngine before the first token.
    """
    from app.openai_compat.providers import ensure_providers_registered
    from app.openai_compat.providers.inference_router import InferenceRouter

    ensure_providers_registered()
    policy = normalize_stream_provider(provider)
    order = stream_fallback_order()
    router = InferenceRouter()
    router.sync_health_ttl()

    if policy == "auto":
        pool = _stream_pool_for_model(model, router)
        ranked = router._rank(
            pool,
            policy=router.active_policy(),
            preferred=router.default_provider(),
        )
        ordered = _dedupe([*ranked, *order])
        healthy, skipped = await filter_healthy_stream_providers(ordered, router=router)
        if not healthy:
            raise no_healthy_provider(model or "", skipped)
        return StreamProviderChain(providers=healthy, skipped_unhealthy=skipped)

    # Explicit override: keep forced provider first even when unhealthy.
    rest = [n for n in order if n != policy]
    healthy_rest, skipped = await filter_healthy_stream_providers(rest, router=router)
    providers = _dedupe([policy, *healthy_rest])
    if not providers:
        raise no_healthy_provider(model or "", skipped)
    return StreamProviderChain(providers=providers, skipped_unhealthy=skipped)


def _dedupe(names: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for n in names:
        key = (n or "").strip().lower()
        if not key or key == "auto" or key in seen:
            continue
        if key not in STREAM_PROVIDER_NAMES:
            continue
        seen.add(key)
        out.append(key)
    return out or ["ollama"]
