"""Default provider + model→provider resolution (Sem03 W1 D2)."""
from __future__ import annotations

from typing import Optional, Tuple

from app.config.settings import settings
from app.openai_compat.errors import model_not_found, unknown_provider
from app.openai_compat.providers.base import ProviderNotFoundError
from app.openai_compat.providers.registry import get_registry


def default_provider_name() -> str:
    return (getattr(settings, "INFERENCE_DEFAULT_PROVIDER", None) or "ollama").strip().lower()


def resolve_provider_name(explicit: Optional[str]) -> str:
    """When provider omitted → default (ollama). Does not validate model."""
    if explicit is None or str(explicit).strip() == "":
        return default_provider_name()
    return str(explicit).strip().lower()


def _model_not_found(model_id: str):
    return model_not_found(model_id)


def _unknown_provider(name: str):
    return unknown_provider(name)


def resolve_provider_for_request(
    *,
    provider: Optional[str],
    model: str,
) -> Tuple[str, object]:
    """
    Resolve (provider_name, provider_instance) for a completion request.

    - Explicit unknown/disabled provider → 400
    - Explicit provider + model not listed by that provider → 404
    - Omitted provider → model→provider map (prefers INFERENCE_DEFAULT_PROVIDER)
    - Unknown model (not in any enabled catalog) → 404
    """
    from app.openai_compat.providers import ensure_providers_registered

    registry = ensure_providers_registered()
    model_id = (model or "").strip()
    if not model_id:
        raise _model_not_found(model_id)

    if provider is not None and str(provider).strip() != "":
        name = str(provider).strip().lower()
        try:
            inst = registry.get(name, require_enabled=True)
        except ProviderNotFoundError as exc:
            raise _unknown_provider(name) from exc
        ids = {m.get("id") for m in inst.models()}
        if model_id not in ids:
            raise _model_not_found(model_id)
        return name, inst

    owner = registry.provider_for_model(model_id)
    if owner is None:
        raise _model_not_found(model_id)
    try:
        inst = registry.get(owner, require_enabled=True)
    except ProviderNotFoundError as exc:
        raise _unknown_provider(owner) from exc
    return owner, inst
