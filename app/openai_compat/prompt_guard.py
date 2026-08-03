"""Prompt injection / model-exfil heuristics (Sem03 W1 D5).

Defense-in-depth only — not a substitute for model-side alignment,
output filtering, or secret management. Heuristic patterns for gateway
edge rejection + interview-ready taxonomy.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable, List, Optional, Sequence

from app.config.settings import settings
from app.openai_compat.errors import openai_error

logger = logging.getLogger(__name__)


class PromptGuardError(ValueError):
    """Raised when a completion request fails the Sem03 prompt guard."""

    def __init__(self, message: str, *, code: str, matched: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.matched = matched


# Classic instruction-override / jailbreak cues (user-controlled text).
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
        r"disregard\s+(the\s+)?(system|developer)\s+(prompt|message|instructions)",
        r"forget\s+(everything|all)\s+(you\s+)?(were\s+)?told",
        r"you\s+are\s+now\s+(dan|jailbroken|unrestricted)",
        r"new\s+(system\s+)?instructions\s*:",
        r"override\s+(your\s+)?(system|safety)\s+(prompt|rules|policy)",
        r"do\s+not\s+follow\s+(your\s+)?(system|developer)\s+instructions",
    )
)

# Attempts to extract hidden prompts, secrets, or model internals.
_EXFIL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(reveal|show|print|dump|repeat)\s+(your\s+)?(system\s+)?(prompt|instructions)",
        r"(what|show)\s+(is|are)\s+your\s+(system|hidden|secret)\s+(prompt|instructions|rules)",
        r"repeat\s+(the\s+)?(text|content)\s+(above|before\s+this)",
        r"(dump|export|exfiltrate)\s+(your\s+)?(weights|parameters|system\s+prompt)",
        r"(show|print|leak)\s+(me\s+)?(the\s+)?(api[_\s-]?key|secret|password|\.env)",
        r"openai_api_key\s*[:=]",
        r"anthropic_api_key\s*[:=]",
        r"base64[-\s]?encode\s+(your\s+)?(system\s+)?(prompt|instructions)",
    )
)


def _guard_enabled() -> bool:
    return bool(getattr(settings, "INFERENCE_PROMPT_GUARD_ENABLED", True))


def _guard_mode() -> str:
    mode = (getattr(settings, "INFERENCE_PROMPT_GUARD_MODE", None) or "block").strip().lower()
    return mode if mode in {"block", "log"} else "block"


def _message_texts(messages: Sequence[Any]) -> List[str]:
    out: List[str] = []
    for m in messages or []:
        if isinstance(m, dict):
            role = str(m.get("role") or "")
            content = m.get("content")
        else:
            role = str(getattr(m, "role", "") or "")
            content = getattr(m, "content", None)
        # Scan user + tool + function content; system is trusted tenant/config input
        # but still scanned for exfil cues pasted into system by clients.
        if role not in {"user", "system", "tool", "function", "assistant"}:
            continue
        if content is None:
            continue
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text") or ""))
                else:
                    parts.append(str(part))
            text = "\n".join(parts)
        else:
            text = str(content)
        if text.strip():
            out.append(text)
    return out


def _first_match(patterns: Iterable[re.Pattern[str]], text: str) -> Optional[re.Match[str]]:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m
    return None


def scan_completion_messages(messages: Sequence[Any]) -> Optional[PromptGuardError]:
    """Return a PromptGuardError if heuristics fire; else None."""
    if not _guard_enabled():
        return None
    for text in _message_texts(messages):
        inj = _first_match(_INJECTION_PATTERNS, text)
        if inj:
            return PromptGuardError(
                "Request blocked: prompt injection pattern detected",
                code="prompt_injection_blocked",
                matched=inj.group(0),
            )
        exfil = _first_match(_EXFIL_PATTERNS, text)
        if exfil:
            return PromptGuardError(
                "Request blocked: model / secret exfiltration pattern detected",
                code="model_exfil_blocked",
                matched=exfil.group(0),
            )
    return None


def assert_safe_completion_messages(messages: Sequence[Any]) -> None:
    """
    Edge guard for /v1/chat/completions.

    Mode `block` (default): raise OpenAI-shaped HTTPException via PromptGuardError
    mapped by caller, or raise openai_error directly.
    Mode `log`: record and allow.
    """
    finding = scan_completion_messages(messages)
    if finding is None:
        return

    logger.warning(
        "inference_prompt_guard code=%s matched=%r mode=%s",
        finding.code,
        finding.matched,
        _guard_mode(),
    )
    if _guard_mode() == "log":
        return

    raise openai_error(
        status_code=400,
        message=str(finding),
        type_="invalid_request_error",
        code=finding.code,
    )
