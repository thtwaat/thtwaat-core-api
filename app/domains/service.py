"""DNS helpers + Domain Manager service."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.domains.models import (
    CompanyDomain,
    DomainStatus,
    DomainVerificationMethod,
    SslStatus,
)
from app.domains.repository import DomainRepository
from app.domains.schemas import (
    DomainCreate,
    DomainDashboardItem,
    DomainDashboardResponse,
    DomainResponse,
    DomainUpdate,
    DomainVerifyResponse,
    SslRequestResponse,
)
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService

logger = logging.getLogger(__name__)

# In-memory CORS origin cache refreshed on domain lifecycle changes
_cors_origin_cache: set[str] = set()
_cors_cache_loaded = False


def invalidate_cors_cache() -> None:
    global _cors_cache_loaded
    _cors_cache_loaded = False


def get_cached_cors_origins(db: Optional[Session] = None) -> List[str]:
    """Merge settings.CORS_ORIGINS with verified custom domain origins."""
    global _cors_origin_cache, _cors_cache_loaded
    static = list(settings.CORS_ORIGINS or [])
    if "*" in static:
        return static

    if not _cors_cache_loaded and db is not None:
        try:
            _cors_origin_cache = set(DomainRepository(db).list_cors_origins())
            _cors_cache_loaded = True
        except Exception as exc:
            logger.warning("cors cache refresh failed: %s", exc)

    merged = list(dict.fromkeys([*static, *_cors_origin_cache]))
    return merged


def _audit(event: str, **fields) -> None:
    logger.info(
        "audit_event=%s %s",
        event,
        " ".join(f"{k}={v}" for k, v in fields.items()),
    )


def generate_verification_token() -> str:
    return f"tht_dom_{secrets.token_urlsafe(24)}"


def platform_host() -> str:
    parsed = urlparse(settings.PUBLIC_API_BASE_URL)
    return parsed.hostname or "api.thtwaat.com"


def cname_target() -> str:
    return getattr(settings, "DOMAIN_CNAME_TARGET", None) or f"cname.{platform_host()}"


def a_records() -> List[str]:
    return list(getattr(settings, "DOMAIN_A_RECORDS", None) or [])


def aaaa_records() -> List[str]:
    return list(getattr(settings, "DOMAIN_AAAA_RECORDS", None) or [])


def build_dns_records(hostname: str, token: str, method: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    txt_host = f"_thtwaat-verify.{hostname}"
    txt_value = f"thtwaat-domain-verification={token}"

    records.append(
        {
            "type": "TXT",
            "host": txt_host,
            "value": txt_value,
            "ttl": 300,
            "purpose": "ownership_verification",
        }
    )

    records.append(
        {
            "type": "CNAME",
            "host": hostname,
            "value": cname_target(),
            "ttl": 300,
            "purpose": "traffic_routing" if method == "CNAME" else "optional_routing",
        }
    )

    for ip in a_records():
        records.append(
            {
                "type": "A",
                "host": hostname,
                "value": ip,
                "ttl": 300,
                "purpose": "ipv4_routing",
            }
        )
    for ip in aaaa_records():
        records.append(
            {
                "type": "AAAA",
                "host": hostname,
                "value": ip,
                "ttl": 300,
                "purpose": "ipv6_routing",
            }
        )
    return records


def widget_urls_for(hostname: str) -> Dict[str, str]:
    base = f"https://{hostname}"
    urls = {
        "root": base,
        "chat_path": f"{base}/chat",
        "widget_embed": f"{base}/public/v1/widget/embed",
        "public_chat": f"{base}/public/v1/chat",
    }
    # If not already a chat.* host, suggest chat subdomain URL
    if hostname.startswith("chat."):
        urls["chat_host"] = base
    else:
        parts = hostname.split(".")
        if len(parts) >= 2:
            root = ".".join(parts[-2:]) if not hostname.startswith("www.") else ".".join(parts[1:][-2:])
            if hostname.startswith("www."):
                root = hostname[4:]
            elif hostname.count(".") == 1:
                root = hostname
            else:
                # app.company.com → company.com
                root = ".".join(parts[1:]) if len(parts) > 2 else hostname
            urls["chat_host"] = f"https://chat.{root}"
        else:
            urls["chat_host"] = f"{base}/chat"
    return urls


def lookup_txt(name: str) -> List[str]:
    """Resolve TXT records. Uses dnspython when available."""
    try:
        import dns.resolver  # type: ignore

        answers = dns.resolver.resolve(name, "TXT")
        out: List[str] = []
        for rdata in answers:
            # TXT may be split into multiple strings
            text = "".join([s.decode() if isinstance(s, bytes) else str(s) for s in rdata.strings])
            out.append(text.strip().strip('"'))
        return out
    except Exception as exc:
        logger.debug("TXT lookup failed for %s: %s", name, exc)
        return []


def lookup_cname(name: str) -> List[str]:
    try:
        import dns.resolver  # type: ignore

        answers = dns.resolver.resolve(name, "CNAME")
        return [str(r.target).rstrip(".").lower() for r in answers]
    except Exception as exc:
        logger.debug("CNAME lookup failed for %s: %s", name, exc)
        return []


class DomainService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DomainRepository(db)

    def _clear_stale_failure(self, domain: CompanyDomain) -> None:
        """Drop leftover simulate/DNS notes once the domain is live with SSL."""
        reason = (domain.failure_reason or "").strip()
        if not reason:
            return
        status_val = domain.status.value if hasattr(domain.status, "value") else str(domain.status)
        ssl_val = str(domain.ssl_status or "").upper()
        stale = "SSL_MODE=simulate" in reason or reason.startswith("DNS not confirmed")
        if status_val == DomainStatus.LIVE.value and stale and ssl_val in ("ACTIVE", "ISSUED"):
            domain.failure_reason = None
            self.repo.save(domain)

    def _to_response(self, domain: CompanyDomain) -> DomainResponse:
        self._clear_stale_failure(domain)
        method = domain.verification_method.value if hasattr(domain.verification_method, "value") else str(domain.verification_method)
        status_val = domain.status.value if hasattr(domain.status, "value") else str(domain.status)
        data = DomainResponse(
            id=domain.id,
            company_id=domain.company_id,
            hostname=domain.hostname,
            status=status_val,
            verification_method=method,
            verification_token=domain.verification_token,
            verified_at=domain.verified_at,
            last_checked_at=domain.last_checked_at,
            failure_reason=domain.failure_reason,
            agent_id=domain.agent_id,
            widget_id=domain.widget_id,
            is_primary=bool(domain.is_primary),
            dns_records=list(domain.dns_records or []),
            ssl_status=domain.ssl_status,
            ssl_issued_at=domain.ssl_issued_at,
            ssl_expires_at=domain.ssl_expires_at,
            ssl_renewal_at=domain.ssl_renewal_at,
            ssl_provider=domain.ssl_provider,
            ssl_challenge=getattr(domain, "ssl_challenge", None) or "http-01",
            certificate_serial=getattr(domain, "certificate_serial", None),
            renew_attempts=int(getattr(domain, "renew_attempts", 0) or 0),
            renewal_error=getattr(domain, "renewal_error", None),
            cors_origin=domain.cors_origin,
            widget_urls=widget_urls_for(domain.hostname),
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
        return data

    def _sync_usage(self, company_id: UUID) -> None:
        count = self.repo.count_for_company(company_id)
        try:
            UsageService(self.db).record(
                company_id,
                UsageDimension.DOMAINS,
                count,
                source="domain_manager",
            )
        except Exception as exc:
            logger.warning("domain usage sync failed: %s", exc)

    def _emit_webhook(self, company_id: UUID, event_type: str, payload: dict) -> None:
        try:
            from app.webhooks.service import WebhookService

            svc = WebhookService(self.db)
            webhooks = svc.repo.get_active_by_company(str(company_id))
            full = {"event": event_type, "data": payload, "company_id": str(company_id)}
            for hook in webhooks:
                types = hook.event_types or []
                if "*" in types or event_type in types:
                    svc._dispatch_worker(hook.url, full, hook.secret)
        except Exception as exc:
            logger.warning("domain webhook emit failed: %s", exc)

    def create(self, company_id: UUID, data: DomainCreate, user_id: UUID) -> DomainResponse:
        hostname = data.hostname
        existing = self.repo.get_by_hostname(hostname)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Domain hostname already registered",
            )

        count = self.repo.count_for_company(company_id)
        UsageService(self.db).check_quota(
            company_id, UsageDimension.DOMAINS, quantity=count + 1
        )

        token = generate_verification_token()
        method = DomainVerificationMethod(data.verification_method)
        records = build_dns_records(hostname, token, method.value)

        if data.is_primary:
            self.repo.clear_primary(company_id)

        domain = CompanyDomain(
            company_id=company_id,
            hostname=hostname,
            status=DomainStatus.PENDING,
            verification_method=method,
            verification_token=token,
            agent_id=data.agent_id,
            widget_id=data.widget_id,
            is_primary=data.is_primary,
            dns_records=records,
            ssl_status=SslStatus.NONE.value,
            cors_origin=f"https://{hostname}",
        )
        domain = self.repo.create(domain)
        self._sync_usage(company_id)
        invalidate_cors_cache()

        _audit(
            "domain_created",
            domain_id=domain.id,
            company_id=company_id,
            user_id=user_id,
            hostname=hostname,
        )
        self._emit_webhook(company_id, "domain.created", {
            "domain_id": str(domain.id),
            "hostname": hostname,
            "status": DomainStatus.PENDING.value,
        })
        return self._to_response(domain)

    def create_free_subdomain(
        self, company_id: UUID, hostname: str, user_id: UUID
    ) -> DomainResponse:
        """Provision a platform-owned *.thtwaat.app subdomain — always free.

        Unlike create(), ownership is never in question (THTWAAT owns the
        zone), so the row is created already VERIFIED/SSL_PENDING instead of
        PENDING, and it deliberately skips the DOMAINS usage-quota check that
        gates customer-added custom domains: a company's plan limit on
        custom domains must never block their free per-project subdomain.
        Progression to LIVE is enqueued immediately and also picked up by
        the next scheduler sweep if the queue is unavailable.
        """
        hostname = hostname.strip().lower().rstrip(".")
        existing = self.repo.get_by_hostname(hostname)
        if existing:
            if existing.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Domain hostname already registered",
                )
            return self._to_response(existing)

        token = generate_verification_token()
        now = datetime.now(timezone.utc)
        domain = CompanyDomain(
            company_id=company_id,
            hostname=hostname,
            status=DomainStatus.SSL_PENDING,
            verification_method=DomainVerificationMethod.TXT,
            verification_token=token,
            verified_at=now,
            last_checked_at=now,
            dns_records=[],
            ssl_status=SslStatus.PENDING.value,
            cors_origin=f"https://{hostname}",
        )
        domain = self.repo.create(domain)
        invalidate_cors_cache()

        _audit(
            "free_subdomain_created",
            domain_id=domain.id,
            company_id=company_id,
            user_id=user_id,
            hostname=hostname,
        )
        self._emit_webhook(company_id, "domain.created", {
            "domain_id": str(domain.id),
            "hostname": hostname,
            "status": domain.status.value,
            "free_subdomain": True,
        })

        try:
            from app.monitoring.queue import enqueue

            enqueue({
                "type": "domain.auto_progress",
                "domain_id": str(domain.id),
            })
        except Exception as exc:
            logger.warning(
                "free_subdomain_enqueue_failed domain_id=%s err=%s", domain.id, exc
            )

        return self._to_response(domain)

    def list(self, company_id: UUID) -> List[DomainResponse]:
        return [self._to_response(d) for d in self.repo.list_for_company(company_id)]

    def get(self, domain_id: UUID, company_id: UUID) -> DomainResponse:
        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        return self._to_response(domain)

    def update(self, domain_id: UUID, company_id: UUID, data: DomainUpdate, user_id: UUID) -> DomainResponse:
        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

        payload = data.model_dump(exclude_unset=True)
        if "is_primary" in payload and payload["is_primary"]:
            self.repo.clear_primary(company_id)
            domain.is_primary = True
        elif "is_primary" in payload:
            domain.is_primary = bool(payload["is_primary"])

        if "agent_id" in payload:
            domain.agent_id = payload["agent_id"]
        if "widget_id" in payload:
            domain.widget_id = payload["widget_id"]
        if "verification_method" in payload and payload["verification_method"]:
            domain.verification_method = DomainVerificationMethod(payload["verification_method"])
            domain.dns_records = build_dns_records(
                domain.hostname,
                domain.verification_token,
                domain.verification_method.value,
            )

        domain = self.repo.save(domain)
        _audit("domain_updated", domain_id=domain.id, company_id=company_id, user_id=user_id)
        return self._to_response(domain)

    def delete(self, domain_id: UUID, company_id: UUID, user_id: UUID) -> None:
        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        hostname = domain.hostname
        self.repo.delete(domain)
        self._sync_usage(company_id)
        invalidate_cors_cache()
        _audit("domain_deleted", domain_id=domain_id, company_id=company_id, user_id=user_id, hostname=hostname)
        self._emit_webhook(company_id, "domain.deleted", {
            "domain_id": str(domain_id),
            "hostname": hostname,
        })

    def dns_instructions(self, domain_id: UUID, company_id: UUID) -> List[Dict[str, Any]]:
        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        return list(domain.dns_records or [])

    def _verify_dns(self, domain: CompanyDomain) -> tuple[bool, str]:
        method = domain.verification_method
        method_val = method.value if hasattr(method, "value") else str(method)
        expected = f"thtwaat-domain-verification={domain.verification_token}"

        # Allow injected override for tests / local simulation
        override = getattr(self, "_dns_override", None)
        if callable(override):
            return override(domain)

        if method_val == "TXT":
            name = f"_thtwaat-verify.{domain.hostname}"
            values = lookup_txt(name)
            if any(expected in v or domain.verification_token in v for v in values):
                return True, "TXT record verified"
            return False, f"TXT record not found at {name}. Expected value containing token."

        # CNAME method: hostname must point to our target AND TXT preferred as secondary
        targets = lookup_cname(domain.hostname)
        expected_cname = cname_target().lower().rstrip(".")
        if any(t.rstrip(".") == expected_cname for t in targets):
            return True, "CNAME record verified"
        return False, f"CNAME for {domain.hostname} must point to {expected_cname}"

    def verify(
        self, domain_id: UUID, company_id: UUID, user_id: UUID, *, auto: bool = False
    ) -> DomainVerifyResponse:
        """Check DNS ownership records.

        auto=True is used by the background scheduler/worker (see progress()):
        a missed check just leaves the domain at DNS_PENDING for the next
        sweep, since DNS propagation can legitimately take hours. auto=False
        (the manual "Verify" action) still fails fast to FAILED so a human
        gets immediate feedback that what they published is wrong.
        """
        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

        domain.status = DomainStatus.DNS_PENDING
        domain.last_checked_at = datetime.now(timezone.utc)
        domain.failure_reason = None
        self.repo.save(domain)

        ok, message = self._verify_dns(domain)
        domain.last_checked_at = datetime.now(timezone.utc)

        if ok:
            domain.status = DomainStatus.VERIFIED
            domain.verified_at = datetime.now(timezone.utc)
            domain.failure_reason = None
            # Auto-advance toward SSL
            domain.status = DomainStatus.SSL_PENDING
            domain.ssl_status = SslStatus.PENDING.value
            self.repo.save(domain)
            invalidate_cors_cache()
            # Refresh cache with this origin immediately
            try:
                global _cors_origin_cache, _cors_cache_loaded
                _cors_origin_cache.add(domain.cors_origin)
                _cors_cache_loaded = True
            except Exception:
                pass

            _audit(
                "domain_verified",
                domain_id=domain.id,
                company_id=company_id,
                user_id=user_id,
                hostname=domain.hostname,
            )
            self._emit_webhook(company_id, "domain.verified", {
                "domain_id": str(domain.id),
                "hostname": domain.hostname,
                "status": domain.status.value,
            })
            return DomainVerifyResponse(
                id=domain.id,
                hostname=domain.hostname,
                status=domain.status.value,
                verified=True,
                message=message + " SSL provisioning pending (Let's Encrypt).",
                dns_records=list(domain.dns_records or []),
            )

        if auto:
            # Not yet propagated — leave it eligible for the next scheduler sweep
            # instead of terminally failing on a single missed check.
            domain.status = DomainStatus.DNS_PENDING
            domain.failure_reason = message
            self.repo.save(domain)
            _audit(
                "domain_verify_pending",
                domain_id=domain.id,
                company_id=company_id,
                reason=message,
            )
            return DomainVerifyResponse(
                id=domain.id,
                hostname=domain.hostname,
                status=domain.status.value,
                verified=False,
                message=message,
                dns_records=list(domain.dns_records or []),
                failure_reason=message,
            )

        domain.status = DomainStatus.FAILED
        domain.failure_reason = message
        self.repo.save(domain)
        _audit(
            "domain_verify_failed",
            domain_id=domain.id,
            company_id=company_id,
            user_id=user_id,
            reason=message,
        )
        return DomainVerifyResponse(
            id=domain.id,
            hostname=domain.hostname,
            status=domain.status.value,
            verified=False,
            message=message,
            dns_records=list(domain.dns_records or []),
            failure_reason=message,
        )

    def retry_verification(self, domain_id: UUID, company_id: UUID, user_id: UUID) -> DomainVerifyResponse:
        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        if domain.status == DomainStatus.LIVE:
            return DomainVerifyResponse(
                id=domain.id,
                hostname=domain.hostname,
                status=domain.status.value,
                verified=True,
                message="Domain already live",
                dns_records=list(domain.dns_records or []),
            )
        domain.status = DomainStatus.PENDING
        domain.failure_reason = None
        self.repo.save(domain)
        return self.verify(domain_id, company_id, user_id)

    def progress(self, domain_id: UUID) -> DomainResponse:
        """Advance a domain one step toward LIVE — the scheduler/worker's
        single entry point for the domain.auto_progress job.

        Dispatches to the existing verify()/request_ssl() based on the
        domain's current status; does nothing for domains already LIVE or
        FAILED. Runs as a background/system action (no authenticated user),
        so it uses the domain's own company_id as the audit actor — the
        same convention scripts/scheduler.py already uses for ssl.renew.
        """
        domain = self.repo.get_by_id(domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

        company_id = domain.company_id
        actor = company_id
        status_val = domain.status.value if hasattr(domain.status, "value") else str(domain.status)

        if status_val in (DomainStatus.PENDING.value, DomainStatus.DNS_PENDING.value):
            self.verify(domain_id, company_id, actor, auto=True)
        elif status_val in (DomainStatus.VERIFIED.value, DomainStatus.SSL_PENDING.value):
            self.request_ssl(domain_id, company_id, actor)

        return self.get(domain_id, company_id)

    def request_ssl(self, domain_id: UUID, company_id: UUID, user_id: UUID) -> SslRequestResponse:
        from app.ssl.manager import SslManager

        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

        needs_dns = domain.verified_at is None and domain.status not in (
            DomainStatus.VERIFIED,
            DomainStatus.SSL_PENDING,
            DomainStatus.LIVE,
        )
        if needs_dns:
            # One-click: verify DNS first, then issue SSL.
            verified = self.verify(domain_id, company_id, user_id)
            if not verified.verified:
                mode = (getattr(settings, "SSL_MODE", None) or "simulate").lower()
                if mode != "simulate":
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            verified.message
                            or "Add the DNS records shown below, click Verify, then Request SSL."
                        ),
                    )
                # Lab/simulate: allow SSL without live DNS so dashboards stay usable.
                domain = self.repo.get_for_company(domain_id, company_id)
                domain.status = DomainStatus.SSL_PENDING
                domain.verified_at = datetime.now(timezone.utc)
                domain.ssl_status = SslStatus.PENDING.value
                domain.failure_reason = None
                self.repo.save(domain)
                logger.warning(
                    "ssl_request_simulate_skip_dns domain_id=%s hostname=%s reason=%s",
                    domain_id,
                    domain.hostname,
                    verified.message,
                )

        result = SslManager(self.db).request(domain_id, company_id, user_id)
        invalidate_cors_cache()
        self._emit_webhook(company_id, "domain.ssl_active", {
            "domain_id": str(domain_id),
            "hostname": result.get("hostname"),
            "ssl_status": result.get("ssl_status"),
        })
        return SslRequestResponse(
            id=domain_id,
            hostname=result["hostname"],
            status=result.get("domain_status") or DomainStatus.LIVE.value,
            ssl_status=result["ssl_status"],
            message=result.get("message") or "SSL certificate issued and nginx vhost generated.",
        )

    def renew_ssl(self, domain_id: UUID, company_id: UUID, user_id: UUID) -> dict:
        from app.ssl.manager import SslManager

        return SslManager(self.db).renew(domain_id, company_id, user_id)

    def ssl_status(self, domain_id: UUID, company_id: UUID) -> dict:
        from app.ssl.manager import SslManager

        return SslManager(self.db).status(domain_id, company_id)

    def mark_ssl_issued(
        self,
        domain_id: UUID,
        company_id: UUID,
        *,
        expires_at: Optional[datetime] = None,
    ) -> DomainResponse:
        """Ops compatibility — delegates to SSL Manager activate path."""
        from app.ssl.manager import SslManager
        from app.ssl.certs import issue_certificate

        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        ok, msg, cert, key, serial, exp = issue_certificate(domain.hostname)
        if not ok:
            raise HTTPException(status_code=502, detail={"error": "ssl_issuance_failed", "message": msg})
        if expires_at:
            exp = expires_at
        SslManager(self.db)._activate(
            domain, cert, key, serial, exp, company_id, event="ssl_issued_ops"
        )
        invalidate_cors_cache()
        self._emit_webhook(company_id, "domain.live", {
            "domain_id": str(domain.id),
            "hostname": domain.hostname,
        })
        return self.get(domain_id, company_id)

    def dashboard(self, company_id: UUID) -> DomainDashboardResponse:
        domains = self.repo.list_for_company(company_id)
        items = []
        for d in domains:
            st = d.status.value if hasattr(d.status, "value") else str(d.status)
            method = d.verification_method.value if hasattr(d.verification_method, "value") else str(d.verification_method)
            items.append(
                DomainDashboardItem(
                    id=d.id,
                    hostname=d.hostname,
                    status=st,
                    ssl_status=d.ssl_status,
                    verification_method=method,
                    is_primary=bool(d.is_primary),
                    dns_records=list(d.dns_records or []),
                    widget_urls=widget_urls_for(d.hostname),
                    cors_origin=d.cors_origin,
                    failure_reason=d.failure_reason,
                    verified_at=d.verified_at,
                    ssl_expires_at=d.ssl_expires_at,
                )
            )

        meter = UsageService(self.db).get_or_create_meter(company_id)
        origins = get_cached_cors_origins(self.db)
        return DomainDashboardResponse(
            company_id=company_id,
            domains=items,
            allowed_origins=origins if "*" not in (settings.CORS_ORIGINS or []) else ["*"],
            max_domains=int(meter.max_domains or 0),
            domains_used=len(domains),
            instructions={
                "add_domain": "POST /api/v1/domains/ with hostname (e.g. chat.company.com)",
                "copy_dns": "Use dns_records from the domain response or GET /api/v1/domains/{id}/dns",
                "verify": "POST /api/v1/domains/{id}/verify after publishing TXT/CNAME",
                "retry": "POST /api/v1/domains/{id}/retry if verification failed",
                "ssl": "POST /api/v1/domains/{id}/ssl/request after DNS verifies",
                "delete": "DELETE /api/v1/domains/{id}",
            },
        )
