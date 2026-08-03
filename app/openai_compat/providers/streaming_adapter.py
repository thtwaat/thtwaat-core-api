"""Common streaming adapter interface (Sem03 W2 D1)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence


@dataclass
class StreamDelta:
    """Normalized incremental unit from any provider stream."""

    content: Optional[str] = None
    role: Optional[str] = None
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    done: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


class StreamingAdapter(ABC):
    """Provider-facing async token stream — cancel must stop upstream generation."""

    name: str = "base"

    @abstractmethod
    async def stream_chat(
        self,
        *,
        model: str,
        messages: Sequence[Dict[str, Any]],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamDelta]:
        """Yield deltas until done (or until cancel())."""
        if False:  # pragma: no cover — make this an async generator type
            yield StreamDelta()

    @abstractmethod
    async def cancel(self) -> None:
        """Stop provider generation immediately (client disconnect)."""


def messages_as_dicts(messages: Sequence[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, dict):
            payload = {"role": m.get("role"), "content": m.get("content")}
            if m.get("name"):
                payload["name"] = m.get("name")
            out.append(payload)
            continue
        payload = {"role": getattr(m, "role", None), "content": getattr(m, "content", None)}
        name = getattr(m, "name", None)
        if name:
            payload["name"] = name
        out.append(payload)
    return out
