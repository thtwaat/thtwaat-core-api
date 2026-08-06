"""Studio deploy domain validation and free *.thtwaat.app subdomains."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

DEFAULT_FREE_ZONE = "thtwaat.app"
DOMAIN_NOT_REGISTERED = "This domain is not registered."


@dataclass
class DomainValidationResult:
    hostname: str
    registered: bool
    reachable: bool
    nxdomain: bool
    is_free_subdomain: bool
    message: str
    records: List[str]
    options: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hostname": self.hostname,
            "registered": self.registered,
            "reachable": self.reachable,
            "nxdomain": self.nxdomain,
            "is_free_subdomain": self.is_free_subdomain,
            "message": self.message,
            "records": self.records,
            "options": self.options,
        }


def free_subdomain_zone() -> str:
    try:
        from app.config.settings import settings

        zone = (getattr(settings, "STUDIO_FREE_SUBDOMAIN_ZONE", None) or DEFAULT_FREE_ZONE).strip()
        return zone.lstrip(".").lower() or DEFAULT_FREE_ZONE
    except Exception:  # noqa: BLE001
        return DEFAULT_FREE_ZONE


def _slug_label(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "app").lower()).strip("-")
    return (cleaned[:28] or "app").strip("-") or "app"


def allocate_free_subdomain(*, project_id: UUID, project_title: str) -> str:
    """Stable unique free hostname: {slug}-{project8}.thtwaat.app"""
    zone = free_subdomain_zone()
    label = f"{_slug_label(project_title)}-{str(project_id).replace('-', '')[:8]}"
    return f"{label}.{zone}".lower()


def is_free_thtwaat_hostname(hostname: str) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    zone = free_subdomain_zone()
    return host == zone or host.endswith(f".{zone}")


def domain_choice_options(*, suggested_free: str) -> List[Dict[str, str]]:
    return [
        {
            "id": "free_subdomain",
            "label": f"Use a free *.{free_subdomain_zone()} subdomain",
            "hostname": suggested_free,
        },
        {
            "id": "custom",
            "label": "Connect an existing custom domain",
            "hostname": "",
        },
    ]


def _lookup_answers(hostname: str) -> tuple[bool, bool, List[str]]:
    """
    Returns (nxdomain, has_records, records).
    nxdomain=True when the name does not exist in DNS.
    """
    host = hostname.strip().lower().rstrip(".")
    records: List[str] = []
    saw_nxdomain = False
    try:
        import dns.resolver  # type: ignore
        import dns.exception  # type: ignore

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 3.0
        for rtype in ("A", "AAAA", "CNAME"):
            try:
                answers = resolver.resolve(host, rtype)
                for rdata in answers:
                    records.append(f"{rtype}:{str(rdata).rstrip('.')}")
            except dns.resolver.NXDOMAIN:
                saw_nxdomain = True
            except (
                dns.resolver.NoAnswer,
                dns.resolver.NoNameservers,
                dns.exception.Timeout,
                dns.resolver.YXDOMAIN,
            ):
                continue
            except Exception as exc:  # noqa: BLE001
                logger.debug("dns_lookup %s %s failed: %s", host, rtype, exc)
        if records:
            return False, True, records
        if saw_nxdomain:
            return True, False, []
        # No answers and no NXDOMAIN → treat as not reachable / not registered for deploy safety
        return True, False, []
    except ImportError:
        # Fallback: socket.getaddrinfo — cannot distinguish NXDOMAIN cleanly
        import socket

        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                records.append(f"ADDR:{info[4][0]}")
            return False, bool(records), records
        except socket.gaierror as exc:
            # EAI_NONAME ~ NXDOMAIN
            if getattr(exc, "errno", None) in {socket.EAI_NONAME, -2, 11001, 8}:
                return True, False, []
            return True, False, []


def validate_hostname(hostname: str, *, suggested_free: Optional[str] = None) -> DomainValidationResult:
    host = (hostname or "").strip().lower().rstrip(".")
    suggested = suggested_free or f"app.{free_subdomain_zone()}"
    options = domain_choice_options(suggested_free=suggested)

    if not host or "." not in host:
        return DomainValidationResult(
            hostname=host,
            registered=False,
            reachable=False,
            nxdomain=True,
            is_free_subdomain=False,
            message=DOMAIN_NOT_REGISTERED,
            records=[],
            options=options,
        )

    free = is_free_thtwaat_hostname(host)
    nxdomain, has_records, records = _lookup_answers(host)

    if nxdomain or not has_records:
        return DomainValidationResult(
            hostname=host,
            registered=False,
            reachable=False,
            nxdomain=True,
            is_free_subdomain=free,
            message=DOMAIN_NOT_REGISTERED,
            records=records,
            options=options,
        )

    return DomainValidationResult(
        hostname=host,
        registered=True,
        reachable=True,
        nxdomain=False,
        is_free_subdomain=free,
        message="Domain is registered and reachable",
        records=records,
        options=options,
    )


def resolve_deploy_hostname(
    *,
    domain_mode: str,
    custom_domain: Optional[str],
    project_id: UUID,
    project_title: str,
) -> tuple[str, str, DomainValidationResult]:
    """
    Returns (hostname, mode, validation).
    mode is free_subdomain | custom.
    """
    mode = (domain_mode or "free_subdomain").strip().lower().replace("-", "_")
    if mode not in {"free_subdomain", "custom"}:
        mode = "free_subdomain"

    free_host = allocate_free_subdomain(project_id=project_id, project_title=project_title)

    if mode == "free_subdomain":
        # Free zone is platform-owned; still validate reachability for Waiting for Domain.
        validation = validate_hostname(free_host, suggested_free=free_host)
        if validation.nxdomain:
            # Platform wildcard may not be resolvable in all envs — still assign hostname,
            # but mark unreachable so status stays waiting_for_domain (not LIVE).
            validation = DomainValidationResult(
                hostname=free_host,
                registered=True,  # zone is ours
                reachable=False,
                nxdomain=False,
                is_free_subdomain=True,
                message="Free subdomain allocated — waiting for DNS to become reachable",
                records=[],
                options=domain_choice_options(suggested_free=free_host),
            )
        else:
            validation = DomainValidationResult(
                hostname=free_host,
                registered=True,
                reachable=True,
                nxdomain=False,
                is_free_subdomain=True,
                message="Free subdomain is reachable",
                records=validation.records,
                options=domain_choice_options(suggested_free=free_host),
            )
        return free_host, "free_subdomain", validation

    custom = (custom_domain or "").strip().lower().rstrip(".")
    validation = validate_hostname(custom, suggested_free=free_host)
    return custom, "custom", validation
