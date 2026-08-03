"""Outbound webhook URL safety (Sem02 W4 Day 5 — SSRF guard)."""
from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Iterable, Optional
from urllib.parse import urlparse

from app.config.settings import settings

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
    }
)


class UnsafeWebhookUrlError(ValueError):
    """Raised when a webhook URL fails the SSRF guard."""


def _webhook_ssrf_enabled() -> bool:
    return bool(getattr(settings, "WEBHOOK_URL_SSRF_GUARD_ENABLED", True))


def _allow_http() -> bool:
    return bool(getattr(settings, "WEBHOOK_ALLOW_HTTP_URLS", False))


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _iter_resolved_ips(hostname: str) -> Iterable[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    infos = socket.getaddrinfo(hostname, None)
    seen: set[str] = set()
    for info in infos:
        addr = info[4][0]
        if addr in seen:
            continue
        seen.add(addr)
        yield ipaddress.ip_address(addr)


def assert_safe_webhook_url(
    url: str,
    *,
    resolve_dns: Optional[bool] = None,
) -> str:
    """
    Validate customer webhook URL before store/deliver.

    Blocks: non-http(s), credentials in URL, localhost/metadata hostnames,
    literal private/link-local IPs, and (when resolving) DNS results that
    land on those ranges.
    """
    if not _webhook_ssrf_enabled():
        return url

    raw = (url or "").strip()
    if not raw:
        raise UnsafeWebhookUrlError("webhook URL is empty")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise UnsafeWebhookUrlError("webhook URL must use https (or http when explicitly allowed)")
    if scheme == "http" and not _allow_http():
        raise UnsafeWebhookUrlError("webhook URL must use https")

    if parsed.username or parsed.password:
        raise UnsafeWebhookUrlError("webhook URL must not contain credentials")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise UnsafeWebhookUrlError("webhook URL missing host")

    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise UnsafeWebhookUrlError(f"webhook host '{host}' is not allowed")

    # Literal IP host
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and _is_blocked_ip(literal):
        raise UnsafeWebhookUrlError(f"webhook IP '{host}' is not allowed")

    do_resolve = (
        bool(getattr(settings, "WEBHOOK_URL_RESOLVE_DNS", True))
        if resolve_dns is None
        else bool(resolve_dns)
    )
    if do_resolve and literal is None:
        try:
            for ip in _iter_resolved_ips(host):
                if _is_blocked_ip(ip):
                    raise UnsafeWebhookUrlError(
                        f"webhook host '{host}' resolves to blocked address {ip}"
                    )
        except socket.gaierror as exc:
            raise UnsafeWebhookUrlError(f"webhook host '{host}' could not be resolved") from exc

    return raw
