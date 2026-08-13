"""Production agent protection helpers (no schema / migration required).

Viral Awaaz is a normal ``AgentConfig`` row identified by its stable production
name/slug — there is no dedicated DB flag. These helpers keep that agent from
being treated as a reusable platform template or created *as* a template via
the new-agent flow, without mutating its prompt/provider/knowledge config.
"""
from __future__ import annotations

from typing import Any, Optional

# Stable production identity — matches how Viral Awaaz is named in ops/tests.
PROTECTED_AGENT_NAMES = frozenset({"Viral Awaaz Assistant"})
PROTECTED_AGENT_SLUGS = frozenset({"viral-awaaz-assistant"})


def is_protected_agent(
    *,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    agent: Any = None,
) -> bool:
    """Return True when the agent matches a protected production identity."""
    if agent is not None:
        name = getattr(agent, "name", None) if name is None else name
        slug = getattr(agent, "slug", None) if slug is None else slug
    n = (name or "").strip()
    s = (slug or "").strip().lower()
    return n in PROTECTED_AGENT_NAMES or s in PROTECTED_AGENT_SLUGS
