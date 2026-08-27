"""THTWAAT Deploy Phase 4B — exact-value secret redaction for deployment logs.

The existing generic ``_SECRET_LIKE`` regex in vite_build.py/nextjs_build.py
(``authorization|token|secret|password|api[_-]?key`` followed by `:`/`=`)
only catches secrets that are logged in a recognizable ``KEY=VALUE`` shape.
It does nothing for a secret VALUE echoed on its own (e.g. a build tool
printing "Using key sk_live_123456" with no `key=` prefix at all) — that is
exactly what this module closes, by redacting the literal secret VALUES for
one deployment out of any text, regardless of surrounding shape.

Callers build the redactor ONCE per deployment, from the same decrypted
values used for build/runtime injection (see env_resolver.py), and apply it
to every log line before it is persisted to StaticSiteDeployment.logs,
emitted over SSE, or attached to an exception. The redactor itself is only
ever handed to the caller as a closure — the underlying secret list is never
logged (str()/repr() of the returned callable reveals nothing) and is
dropped as soon as it goes out of scope.
"""
from __future__ import annotations

import re
from typing import Callable, List, Sequence

REDACTED_PLACEHOLDER = "[REDACTED]"

# A secret value this short is either empty-ish or so generic that redacting
# it would mangle unrelated log text (e.g. a secret of "a" would blank every
# letter "a" in the build log) — not realistic for a real credential, but a
# floor here keeps a pathological short "secret" from making logs useless.
_MIN_REDACTABLE_LEN = 4


def build_secret_redactor(secrets: Sequence[str]) -> Callable[[str], str]:
    """Returns a function that replaces every occurrence of any given secret
    value with REDACTED_PLACEHOLDER. Longest-first so one secret that
    happens to be a substring of another is still fully covered."""
    unique_secrets = sorted({s for s in secrets if s and len(s) >= _MIN_REDACTABLE_LEN}, key=len, reverse=True)
    if not unique_secrets:
        return lambda text: text

    pattern = re.compile("|".join(re.escape(s) for s in unique_secrets))

    def _redact(text: str) -> str:
        if not text:
            return text
        return pattern.sub(REDACTED_PLACEHOLDER, text)

    return _redact


def redact_lines(lines: List[str], redactor: Callable[[str], str]) -> List[str]:
    return [redactor(line) for line in (lines or [])]
