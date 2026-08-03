"""TTL cache for provider health probes (Sem03 W1 D3)."""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple


class ProviderHealthCache:
    """In-process health cache — skip repeated probes within TTL."""

    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = max(0.0, float(ttl_seconds))
        self._entries: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    @property
    def ttl_seconds(self) -> float:
        return self._ttl

    def set_ttl(self, ttl_seconds: float) -> None:
        self._ttl = max(0.0, float(ttl_seconds))

    def clear(self) -> None:
        self._entries.clear()

    def invalidate(self, provider: str) -> None:
        self._entries.pop((provider or "").strip().lower(), None)

    def get_cached(self, provider: str) -> Optional[Dict[str, Any]]:
        key = (provider or "").strip().lower()
        row = self._entries.get(key)
        if row is None:
            return None
        expires_at, payload = row
        if self._ttl <= 0 or time.monotonic() >= expires_at:
            self._entries.pop(key, None)
            return None
        return dict(payload)

    def put(self, provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        key = (provider or "").strip().lower()
        stored = dict(payload)
        self._entries[key] = (time.monotonic() + self._ttl, stored)
        return stored

    async def get_or_probe(
        self,
        provider: str,
        probe: Callable[[], Awaitable[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        cached = self.get_cached(provider)
        if cached is not None:
            out = dict(cached)
            out["cached"] = True
            return out
        try:
            result = await probe()
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "error": str(exc)}
        stored = self.put(provider, result if isinstance(result, dict) else {"ok": False})
        out = dict(stored)
        out["cached"] = False
        return out


_HEALTH_CACHE = ProviderHealthCache(ttl_seconds=30.0)


def get_health_cache() -> ProviderHealthCache:
    return _HEALTH_CACHE


def reset_health_cache_for_tests(ttl_seconds: float = 30.0) -> ProviderHealthCache:
    global _HEALTH_CACHE
    _HEALTH_CACHE = ProviderHealthCache(ttl_seconds=ttl_seconds)
    return _HEALTH_CACHE
