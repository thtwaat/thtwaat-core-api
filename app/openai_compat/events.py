"""Completion webhook event names and payloads (Week 3 Day 1)."""
from __future__ import annotations

from typing import Any, Dict, Optional

EVENT_COMPLETION_SUCCEEDED = "completion.succeeded"
EVENT_COMPLETION_FAILED = "completion.failed"

COMPLETION_EVENTS = frozenset({EVENT_COMPLETION_SUCCEEDED, EVENT_COMPLETION_FAILED})


def build_completion_event_data(
    *,
    completion_id: str,
    model: str,
    status: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: Optional[int] = None,
    error: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    total = int(prompt_tokens) + int(completion_tokens)
    return {
        "completion_id": completion_id,
        "model": model,
        "status": status,
        "provider": provider,
        "usage": {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": total,
        },
        "latency_ms": latency_ms,
        "error": error,
    }
