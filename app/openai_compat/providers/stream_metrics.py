"""In-process streaming metrics (Sem03 W2 D1–D3 reliability + health)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StreamRunMetrics:
    first_token_latency_ms: Optional[float] = None
    total_stream_duration_ms: float = 0.0
    streamed_tokens: int = 0
    cancelled: bool = False
    error: Optional[str] = None
    provider: str = ""
    # Day 2 counters / context
    fallback_used: bool = False
    providers_tried: List[str] = field(default_factory=list)
    provider_latency_ms: Optional[float] = None
    finish_reason: Optional[str] = None
    request_id: Optional[str] = None
    tenant_id: Optional[str] = None
    outcome: str = "completed"  # started|completed|cancelled|failed
    # Day 3 — health-aware routing
    health_skipped: int = 0
    skipped_unhealthy: List[str] = field(default_factory=list)


class StreamingMetrics:
    def __init__(self) -> None:
        self.runs: List[StreamRunMetrics] = []
        self.first_token_latency_ms: List[float] = []
        self.total_stream_duration_ms: List[float] = []
        self.streamed_tokens_total: int = 0
        self.stream_started: int = 0
        self.stream_completed: int = 0
        self.stream_cancelled: int = 0
        self.stream_failed: int = 0
        self.fallback_used: int = 0
        self.health_skipped: int = 0
        self.stream_providers_unhealthy: int = 0
        self.provider_latency_ms: List[float] = []
        self.cancels: int = 0
        self.errors: Dict[str, int] = defaultdict(int)
        self.by_provider: Dict[str, int] = defaultdict(int)

    def reset(self) -> None:
        self.runs.clear()
        self.first_token_latency_ms.clear()
        self.total_stream_duration_ms.clear()
        self.streamed_tokens_total = 0
        self.stream_started = 0
        self.stream_completed = 0
        self.stream_cancelled = 0
        self.stream_failed = 0
        self.fallback_used = 0
        self.health_skipped = 0
        self.stream_providers_unhealthy = 0
        self.provider_latency_ms.clear()
        self.cancels = 0
        self.errors.clear()
        self.by_provider.clear()

    def mark_started(self) -> None:
        self.stream_started += 1

    def record_health_skipped(self, count: int) -> None:
        self.health_skipped += max(0, int(count))

    def mark_provider_unhealthy(self, provider: str = "") -> None:
        self.stream_providers_unhealthy += 1
        if provider:
            self.errors[f"unhealthy:{provider}"] += 1

    def record(self, run: StreamRunMetrics) -> None:
        self.runs.append(run)
        self.by_provider[run.provider or "unknown"] += 1
        if run.first_token_latency_ms is not None:
            self.first_token_latency_ms.append(float(run.first_token_latency_ms))
        self.total_stream_duration_ms.append(float(run.total_stream_duration_ms))
        self.streamed_tokens_total += int(run.streamed_tokens or 0)
        if run.provider_latency_ms is not None:
            self.provider_latency_ms.append(float(run.provider_latency_ms))
        if run.fallback_used:
            self.fallback_used += 1
        if run.cancelled or run.outcome == "cancelled":
            self.cancels += 1
            self.stream_cancelled += 1
        elif run.outcome == "failed" or run.error:
            self.stream_failed += 1
        else:
            self.stream_completed += 1
        if run.error:
            self.errors[run.error] += 1

    def snapshot(self) -> Dict[str, Any]:
        def _avg(values: List[float]) -> float | None:
            if not values:
                return None
            return round(sum(values) / len(values), 3)

        last = self.runs[-1] if self.runs else None
        return {
            "stream_started": self.stream_started,
            "stream_completed": self.stream_completed,
            "stream_cancelled": self.stream_cancelled,
            "stream_failed": self.stream_failed,
            "fallback_used": self.fallback_used,
            "health_skipped": self.health_skipped,
            "stream_providers_unhealthy": self.stream_providers_unhealthy,
            "tokens_streamed": self.streamed_tokens_total,
            "provider_latency_ms": {
                "count": len(self.provider_latency_ms),
                "avg": _avg(self.provider_latency_ms),
                "last": last.provider_latency_ms if last else None,
            },
            "first_token_latency_ms": {
                "count": len(self.first_token_latency_ms),
                "avg": _avg(self.first_token_latency_ms),
                "last": last.first_token_latency_ms if last else None,
            },
            "total_stream_duration_ms": {
                "count": len(self.total_stream_duration_ms),
                "avg": _avg(self.total_stream_duration_ms),
                "last": last.total_stream_duration_ms if last else None,
            },
            "streamed_tokens": {
                "total": self.streamed_tokens_total,
                "last": last.streamed_tokens if last else None,
            },
            "cancels": self.cancels,
            "errors": dict(self.errors),
            "by_provider": dict(self.by_provider),
        }


_STREAM_METRICS = StreamingMetrics()


def get_streaming_metrics() -> StreamingMetrics:
    return _STREAM_METRICS


def reset_streaming_metrics_for_tests() -> StreamingMetrics:
    _STREAM_METRICS.reset()
    return _STREAM_METRICS
