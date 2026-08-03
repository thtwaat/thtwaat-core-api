"""In-process streaming metrics (Sem03 W2 D1)."""
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


class StreamingMetrics:
    def __init__(self) -> None:
        self.runs: List[StreamRunMetrics] = []
        self.first_token_latency_ms: List[float] = []
        self.total_stream_duration_ms: List[float] = []
        self.streamed_tokens_total: int = 0
        self.cancels: int = 0
        self.errors: Dict[str, int] = defaultdict(int)
        self.by_provider: Dict[str, int] = defaultdict(int)

    def reset(self) -> None:
        self.runs.clear()
        self.first_token_latency_ms.clear()
        self.total_stream_duration_ms.clear()
        self.streamed_tokens_total = 0
        self.cancels = 0
        self.errors.clear()
        self.by_provider.clear()

    def record(self, run: StreamRunMetrics) -> None:
        self.runs.append(run)
        self.by_provider[run.provider or "unknown"] += 1
        if run.first_token_latency_ms is not None:
            self.first_token_latency_ms.append(float(run.first_token_latency_ms))
        self.total_stream_duration_ms.append(float(run.total_stream_duration_ms))
        self.streamed_tokens_total += int(run.streamed_tokens or 0)
        if run.cancelled:
            self.cancels += 1
        if run.error:
            self.errors[run.error] += 1

    def snapshot(self) -> Dict[str, Any]:
        def _avg(values: List[float]) -> float | None:
            if not values:
                return None
            return round(sum(values) / len(values), 3)

        last = self.runs[-1] if self.runs else None
        return {
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
