"""THTWAAT Deploy Phase 6A — deterministic, collision-safe preview hostnames.

Previews ALWAYS live on the platform-owned free-subdomain zone, NEVER a
customer's own custom domain — even if the site's production deployment
uses one. That's a deliberate security/ops boundary (never touch a
customer's DNS/cert for ephemeral PR content) and it's what keeps "no
second certificate system" trivially true: allocate_preview_subdomain()'s
output is fed straight into the SAME bind_hostname_and_ssl(mode=
"free_subdomain", ...) call production's free-subdomain path already uses.
"""
from __future__ import annotations

import re
from uuid import UUID

from app.config.settings import settings
from app.studio.domain_validation import free_subdomain_zone

PREVIEW_LABEL_MAX_LEN = 48


def _slug_label(value: str) -> str:
    # Local copy of app.studio.domain_validation's private _slug_label — not
    # imported since that name is an internal helper of that module, not a
    # published API; duplicating 3 lines beats depending on another module's
    # private symbol staying stable.
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "app").lower()).strip("-")
    return (cleaned[:28] or "app").strip("-") or "app"


def _preview_prefix() -> str:
    prefix = (getattr(settings, "PREVIEW_SUBDOMAIN_PREFIX", None) or "pr").strip().lower()
    # Only lowercase alnum survives into a DNS label; a misconfigured
    # setting must never produce an invalid or surprising hostname.
    cleaned = "".join(c for c in prefix if c.isalnum()) or "pr"
    return cleaned


def allocate_preview_subdomain(*, site_id: UUID, site_name: str, pr_number: int) -> str:
    """Stable hostname for one (site, PR): pr-{n}-{slug}-{site8}.{zone}.

    Deterministic per (site_id, pr_number) — synchronize/reopen reuse the
    IDENTICAL hostname (no wasted allocations, no cert churn between
    generations of the same PR). Structurally distinct from
    allocate_free_subdomain()'s "{slug}-{site8}.{zone}" production scheme
    (that function never emits a "pr-" prefix), so a preview hostname can
    never collide with a production one.
    """
    zone = free_subdomain_zone()
    prefix = _preview_prefix()
    pr = max(0, int(pr_number))
    label = f"{prefix}-{pr}-{_slug_label(site_name)}-{str(site_id).replace('-', '')[:8]}"
    label = label[:PREVIEW_LABEL_MAX_LEN].rstrip("-") or f"{prefix}-{pr}"
    return f"{label}.{zone}".lower()


def is_preview_hostname(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    prefix = _preview_prefix()
    return host.startswith(f"{prefix}-")
