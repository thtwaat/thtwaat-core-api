"""Deterministic stub completions for CI / local without provider keys."""
from __future__ import annotations

from typing import List

from app.openai_compat.schemas import ChatMessage


def estimate_tokens(text: str) -> int:
    # Rough heuristic (~4 chars/token) — good enough for Day 1 metering scaffolding
    return max(1, len(text or "") // 4)


def stub_complete(messages: List[ChatMessage], *, model: str) -> tuple[str, int, int]:
    last_user = ""
    for m in reversed(messages):
        if m.role == "user" and m.content:
            if isinstance(m.content, str):
                last_user = m.content
            else:
                last_user = str(m.content)
            break
    content = (
        f"[thtwaat-stub:{model}] "
        f"I received your message ({len(last_user)} chars). "
        "Live inference is available when OPENAI_COMPAT_INFERENCE=gateway."
    )
    prompt_tokens = sum(
        estimate_tokens(m.content if isinstance(m.content, str) else str(m.content or ""))
        for m in messages
    )
    completion_tokens = estimate_tokens(content)
    return content, prompt_tokens, completion_tokens
