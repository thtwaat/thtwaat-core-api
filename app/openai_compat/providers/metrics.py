"""In-process inference routing metrics (Sem03 W1 D3)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


class InferenceRoutingMetrics:
    """Counters/observations for router decisions — not Prometheus export yet."""

    def __init__(self) -> None:
        self.provider_selected: Dict[str, int] = defaultdict(int)
        self.provider_errors: Dict[str, int] = defaultdict(int)
        self.provider_latency_ms: Dict[str, List[float]] = defaultdict(list)
        self.routing_time_ms: List[float] = []
        self.policy_selected: Dict[str, int] = defaultdict(int)

    def reset(self) -> None:
        self.provider_selected.clear()
        self.provider_errors.clear()
        self.provider_latency_ms.clear()
        self.routing_time_ms.clear()
        self.policy_selected.clear()

    def record_selection(self, provider: str, *, policy: str, routing_time_ms: float) -> None:
        name = (provider or "unknown").strip().lower() or "unknown"
        self.provider_selected[name] += 1
        self.policy_selected[(policy or "default").strip().lower()] += 1
        self.routing_time_ms.append(float(routing_time_ms))

    def record_latency(self, provider: str, latency_ms: float) -> None:
        name = (provider or "unknown").strip().lower() or "unknown"
        self.provider_latency_ms[name].append(float(latency_ms))

    def record_error(self, provider: str) -> None:
        name = (provider or "unknown").strip().lower() or "unknown"
        self.provider_errors[name] += 1

    def snapshot(self) -> Dict[str, Any]:
        def _avg(values: List[float]) -> float | None:
            if not values:
                return None
            return round(sum(values) / len(values), 3)

        return {
            "provider_selected": dict(self.provider_selected),
            "provider_errors": dict(self.provider_errors),
            "provider_latency_ms": {
                k: {"count": len(v), "avg": _avg(v), "last": v[-1] if v else None}
                for k, v in self.provider_latency_ms.items()
            },
            "routing_time_ms": {
                "count": len(self.routing_time_ms),
                "avg": _avg(self.routing_time_ms),
                "last": self.routing_time_ms[-1] if self.routing_time_ms else None,
            },
            "policy_selected": dict(self.policy_selected),
        }


_METRICS = InferenceRoutingMetrics()


def get_routing_metrics() -> InferenceRoutingMetrics:
    return _METRICS


def reset_routing_metrics_for_tests() -> InferenceRoutingMetrics:
    _METRICS.reset()
    return _METRICS
