"""Stream provider routing — auto + explicit + fallback chain (Sem03 W2 D2)."""
from __future__ import annotations

from typing import List, Optional, Sequence

from app.config.settings import settings
from app.openai_compat.errors import openai_error

STREAM_PROVIDER_POLICIES = frozenset(
    {"auto", "ollama", "openai", "gemini", "anthropic"}
)


def stream_fallback_order() -> List[str]:
    raw = getattr(settings, "STREAM_FALLBACK_ORDER", None) or "ollama,openai,gemini,anthropic"
    out: List[str] = []
    for part in str(raw).split(","):
        name = part.strip().lower()
        if name and name in STREAM_PROVIDER_POLICIES and name != "auto" and name not in out:
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


async def resolve_stream_provider_chain(
    *,
    model: str,
    provider: Optional[str],
) -> List[str]:
    """
    Build ordered provider attempt list for a stream request.

    - provider=auto → health-aware primary from InferenceRouter, then STREAM_FALLBACK_ORDER
    - provider=<name> → that name first, then remaining fallbacks
    Fallback is only used by StreamEngine before the first token.
    """
    policy = normalize_stream_provider(provider)
    order = stream_fallback_order()

    if policy == "auto":
        primary: Optional[str] = None
        try:
            from app.openai_compat.inference_routing_service import InferenceRoutingService
            from app.openai_compat.providers.capabilities import ProviderCapability

            decision = await InferenceRoutingService().select_provider(
                model=model,
                provider=None,
                capability=ProviderCapability.CHAT,
            )
            cand = (decision.provider_name or "").strip().lower()
            if cand in STREAM_PROVIDER_POLICIES and cand != "auto":
                primary = cand
        except Exception:  # noqa: BLE001 — fall back to configured order
            primary = None
        if primary is None:
            primary = order[0] if order else "ollama"
        return _dedupe([primary, *order])

    return _dedupe([policy, *order])


def _dedupe(names: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for n in names:
        key = (n or "").strip().lower()
        if not key or key == "auto" or key in seen:
            continue
        if key not in STREAM_PROVIDER_POLICIES:
            continue
        seen.add(key)
        out.append(key)
    return out or ["ollama"]
