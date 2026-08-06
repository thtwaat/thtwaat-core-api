"""Workspace / company slug helpers — generate URL-safe unique slugs from names."""
from __future__ import annotations

import re
import secrets
from typing import Callable, Optional


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify_company_name(name: str, *, max_length: int = 80) -> str:
    """
    ``Asma Garments`` → ``asma-garments``.

    Falls back to ``workspace`` when the name has no usable characters.
    """
    raw = (name or "").strip().lower()
    slug = _SLUG_RE.sub("-", raw).strip("-")
    if not slug:
        slug = "workspace"
    # Collapse duplicate hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:max_length].strip("-") or "workspace"


def allocate_unique_slug(
    name: str,
    *,
    slug_exists: Callable[[str], bool],
    preferred: Optional[str] = None,
    max_length: int = 100,
) -> str:
    """
    Return an unused slug derived from ``name`` (or ``preferred`` if provided).

    Collision strategy:
    1. ``asma-garments``
    2. ``asma-garments-2``, ``asma-garments-3``, …
    3. ``asma-garments-a4f3`` (hex suffix) if numeric suffixes are exhausted
    """
    base = slugify_company_name(preferred or name, max_length=min(80, max_length - 12))
    if not slug_exists(base):
        return base

    for n in range(2, 50):
        candidate = f"{base}-{n}"
        if len(candidate) > max_length:
            candidate = f"{base[: max_length - len(str(n)) - 1]}-{n}"
        if not slug_exists(candidate):
            return candidate

    for _ in range(16):
        suffix = secrets.token_hex(2)  # e.g. a4f3
        candidate = f"{base}-{suffix}"
        if len(candidate) > max_length:
            candidate = f"{base[: max_length - 5]}-{suffix}"
        if not slug_exists(candidate):
            return candidate

    # Extremely unlikely — last resort random workspace id
    return f"ws-{secrets.token_hex(4)}"
