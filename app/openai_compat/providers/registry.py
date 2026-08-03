"""Dynamic inference provider registry (Sem03 W1 D2)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from app.openai_compat.providers.base import (
    InferenceProvider,
    ProviderNotFoundError,
)

logger = logging.getLogger(__name__)


class InferenceProviderRegistry:
    """Register provider classes; instantiate enabled ones on demand."""

    def __init__(self) -> None:
        self._classes: Dict[str, Type[InferenceProvider]] = {}
        self._instances: Dict[str, InferenceProvider] = {}

    def register(self, name: str, provider_cls: Type[InferenceProvider]) -> None:
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("provider name required")
        self._classes[key] = provider_cls
        self._instances.pop(key, None)
        logger.debug("inference provider registered name=%s", key)

    def unregister(self, name: str) -> None:
        key = (name or "").strip().lower()
        self._classes.pop(key, None)
        self._instances.pop(key, None)

    def clear(self) -> None:
        self._classes.clear()
        self._instances.clear()

    def registered_names(self) -> List[str]:
        return sorted(self._classes.keys())

    def get_class(self, name: str) -> Type[InferenceProvider]:
        key = (name or "").strip().lower()
        if key not in self._classes:
            raise ProviderNotFoundError(f"Provider '{name}' is not registered")
        return self._classes[key]

    def get(self, name: str, *, require_enabled: bool = True) -> InferenceProvider:
        key = (name or "").strip().lower()
        if key not in self._classes:
            raise ProviderNotFoundError(f"Provider '{name}' is not registered")
        if key not in self._instances:
            self._instances[key] = self._classes[key]()
        inst = self._instances[key]
        if require_enabled and not inst.is_enabled():
            raise ProviderNotFoundError(f"Provider '{name}' is disabled")
        return inst

    def enabled_providers(self) -> List[InferenceProvider]:
        out: List[InferenceProvider] = []
        for name in self.registered_names():
            try:
                inst = self.get(name, require_enabled=False)
            except ProviderNotFoundError:
                continue
            if inst.is_enabled():
                out.append(inst)
        return out

    def enabled_names(self) -> List[str]:
        return [p.name for p in self.enabled_providers()]

    def all_enabled_models(self) -> List[Dict[str, Any]]:
        """Merge model catalogs from enabled providers (last id wins)."""
        seen: Dict[str, Dict[str, Any]] = {}
        for prov in self.enabled_providers():
            for item in prov.models():
                mid = item.get("id")
                if not mid:
                    continue
                row = dict(item)
                row.setdefault("owned_by", prov.name)
                row["_provider"] = prov.name
                seen[str(mid)] = row
        return list(seen.values())

    def provider_for_model(self, model_id: str) -> Optional[str]:
        """Return enabled provider name that lists this model id."""
        needle = (model_id or "").strip()
        if not needle:
            return None
        # Prefer default provider if it owns the model
        from app.config.settings import settings

        default = (getattr(settings, "INFERENCE_DEFAULT_PROVIDER", None) or "ollama").strip().lower()
        owners: List[str] = []
        for prov in self.enabled_providers():
            for item in prov.models():
                if item.get("id") == needle:
                    owners.append(prov.name)
                    break
        if not owners:
            return None
        if default in owners:
            return default
        return owners[0]

    async def aggregate_health(self) -> Dict[str, Any]:
        """Health of enabled providers; overall ok if ≥1 provider ok OR none enabled."""
        details: Dict[str, Any] = {}
        ok_count = 0
        enabled = self.enabled_providers()
        for prov in enabled:
            try:
                h = await prov.health()
            except Exception as exc:  # noqa: BLE001
                h = {"ok": False, "error": str(exc)}
            details[prov.name] = h
            if h.get("ok"):
                ok_count += 1
        return {
            "ok": ok_count > 0 or len(enabled) == 0,
            "enabled": [p.name for p in enabled],
            "healthy_count": ok_count,
            "providers": details,
        }


_REGISTRY = InferenceProviderRegistry()


def get_registry() -> InferenceProviderRegistry:
    return _REGISTRY


def reset_registry_for_tests() -> InferenceProviderRegistry:
    """Clear and return the singleton (unit tests only)."""
    _REGISTRY.clear()
    return _REGISTRY
