"""Shared helpers for Sem03 inference providers."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

from app.openai_compat.inference_adapter import new_completion_id


def model_entry(model_id: str, owned_by: str, *, created: int | None = None) -> Dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "created": created if created is not None else 1_720_000_000,
        "owned_by": owned_by,
    }


def synthetic_chat_completion(
    *,
    provider: str,
    model: str,
    messages: Sequence[Dict[str, Any]],
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """Day-2 cloud providers: OpenAI-shaped response without remote HTTP."""
    last = ""
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            last = str(m.get("content"))
    text = content or f"[{provider}] routed ok for model={model} (sem03-w1-d2)"
    if last and content is None:
        text = f"[{provider}] {last[:200]}"
    return {
        "id": new_completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": max(1, len(last) // 4),
            "completion_tokens": max(1, len(text) // 4),
            "total_tokens": max(2, (len(last) + len(text)) // 4),
        },
        "system_fingerprint": f"thtwaat-{provider}",
    }


def synthetic_embeddings(
    *,
    model: str,
    input: Any,
    dims: int = 8,
) -> Dict[str, Any]:
    texts = input if isinstance(input, list) else [input]
    data = []
    for i, _ in enumerate(texts):
        data.append(
            {
                "object": "embedding",
                "index": i,
                "embedding": [float((i + 1) % 7) * 0.01] * dims,
            }
        )
    return {"object": "list", "data": data, "model": model, "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)}}
