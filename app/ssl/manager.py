"""SSL Manager — request, renew, status, expiry monitoring."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domains.models import CompanyDomain, DomainStatus, SslStatus, SslChallengeType
from app.domains.repository import DomainRepository
from app.ssl.certs import issue_certificate, read_cert_expiry
from app.ssl.nginx_gen import generate_vhost, reload_nginx, remove_vhost

logger = logging.getLogger(__name__)

_LEGACY_SSL = {
    "none": SslStatus.NONE.value,
    "pending": SslStatus.PENDING.value,
    "issued": SslStatus.ISSUED.value,
    "renewing": SslStatus.RENEWING.value,
    "expired": SslStatus.EXPIRED.value,
    "failed": SslStatus.FAILED.value,
}


def normalize_ssl_status(value: Optional[str]) -> str:
    if not value:
        return SslStatus.NONE.value
    v = str(value)
    if v in _LEGACY_SSL:
        return _LEGACY_SSL[v]
    return v.upper()


class SslManager:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DomainRepository(db)

    def _get(self, domain_id: UUID, company_id: UUID) -> CompanyDomain:
        domain = self.repo.get_for_company(domain_id, company_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")
        return domain

    def _audit(self, event: str, **fields) -> None:
        logger.info("audit_event=%s %s", event, " ".join(f"{k}={v}" for k, v in fields.items()))

    def status(self, domain_id: UUID, company_id: UUID) -> Dict[str, Any]:
        domain = self._get(domain_id, company_id)
        now = datetime.now(timezone.utc)
        expires = domain.ssl_expires_at
        days_left = None
        if expires:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            days_left = max(0, int((expires - now).total_seconds() // 86400))
            # Auto-mark expired
            if expires <= now and normalize_ssl_status(domain.ssl_status) not in (
                SslStatus.EXPIRED.value,
                SslStatus.NONE.value,
            ):
                domain.ssl_status = SslStatus.EXPIRED.value
                self.repo.save(domain)

        return {
            "domain_id": str(domain.id),
            "hostname": domain.hostname,
            "ssl_status": normalize_ssl_status(domain.ssl_status),
            "ssl_challenge": domain.ssl_challenge or SslChallengeType.HTTP_01.value,
            "certificate_serial": domain.certificate_serial,
            "issued_at": domain.ssl_issued_at.isoformat() if domain.ssl_issued_at else None,
            "expires_at": domain.ssl_expires_at.isoformat() if domain.ssl_expires_at else None,
            "renewal_at": domain.ssl_renewal_at.isoformat() if domain.ssl_renewal_at else None,
            "last_checked_at": (
                domain.ssl_last_checked_at.isoformat() if domain.ssl_last_checked_at else None
            ),
            "renew_attempts": int(domain.renew_attempts or 0),
            "renewal_error": domain.renewal_error,
            "days_until_expiry": days_left,
            "cert_path": domain.cert_path,
            "key_path": domain.key_path,
            "nginx_config_path": domain.nginx_config_path,
            "is_wildcard": bool(domain.is_wildcard),
            "provider": domain.ssl_provider or "letsencrypt",
            "domain_status": domain.status.value if hasattr(domain.status, "value") else str(domain.status),
        }

    def request(
        self,
        domain_id: UUID,
        company_id: UUID,
        user_id: UUID,
        *,
        challenge: str = "http-01",
        wildcard: bool = False,
    ) -> Dict[str, Any]:
        domain = self._get(domain_id, company_id)
        if domain.verified_at is None and domain.status not in (
            DomainStatus.VERIFIED,
            DomainStatus.SSL_PENDING,
            DomainStatus.LIVE,
        ):
            raise HTTPException(
                status_code=400,
                detail="Domain must be DNS-verified before requesting SSL",
            )

        if challenge == "dns-01" or wildcard:
            domain.ssl_challenge = SslChallengeType.DNS_01.value
            domain.is_wildcard = True
        else:
            domain.ssl_challenge = SslChallengeType.HTTP_01.value

        domain.ssl_status = SslStatus.REQUESTING.value
        domain.status = DomainStatus.SSL_PENDING
        domain.renewal_error = None
        domain.ssl_last_checked_at = datetime.now(timezone.utc)
        self.repo.save(domain)

        ok, msg, cert, key, serial, expires = issue_certificate(
            domain.hostname, wildcard=bool(domain.is_wildcard)
        )

        if not ok:
            domain.ssl_status = SslStatus.FAILED.value
            domain.renewal_error = msg
            domain.renew_attempts = int(domain.renew_attempts or 0) + 1
            self.repo.save(domain)
            self._audit("ssl_request_failed", domain_id=domain.id, reason=msg)
            raise HTTPException(status_code=502, detail={"error": "ssl_issuance_failed", "message": msg})

        return self._activate(domain, cert, key, serial, expires, user_id, event="ssl_issued")

    def renew(self, domain_id: UUID, company_id: UUID, user_id: UUID) -> Dict[str, Any]:
        domain = self._get(domain_id, company_id)
        domain.ssl_status = SslStatus.RENEWING.value
        domain.ssl_last_checked_at = datetime.now(timezone.utc)
        domain.renew_attempts = int(domain.renew_attempts or 0) + 1
        self.repo.save(domain)

        ok, msg, cert, key, serial, expires = issue_certificate(
            domain.hostname, wildcard=bool(domain.is_wildcard)
        )
        if not ok:
            domain.ssl_status = SslStatus.FAILED.value
            domain.renewal_error = msg
            self.repo.save(domain)
            self._audit("ssl_renew_failed", domain_id=domain.id, attempt=domain.renew_attempts, reason=msg)
            # Retry budget — leave FAILED for scheduler to retry later
            raise HTTPException(status_code=502, detail={"error": "ssl_renew_failed", "message": msg, "attempts": domain.renew_attempts})

        return self._activate(domain, cert, key, serial, expires, user_id, event="ssl_renewed")

    def _activate(self, domain, cert, key, serial, expires, user_id, event: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        domain.ssl_status = SslStatus.ACTIVE.value
        domain.ssl_issued_at = now
        domain.ssl_expires_at = expires or (now + timedelta(days=90))
        domain.ssl_renewal_at = domain.ssl_expires_at - timedelta(days=30)
        domain.certificate_serial = serial
        domain.cert_path = str(cert) if cert else domain.cert_path
        domain.key_path = str(key) if key else domain.key_path
        domain.renewal_error = None
        domain.ssl_last_checked_at = now
        domain.ssl_provider = "letsencrypt"
        domain.status = DomainStatus.LIVE

        if domain.cert_path and domain.key_path:
            conf = generate_vhost(
                domain.hostname,
                domain.cert_path,
                domain.key_path,
                include_www=domain.hostname.count(".") == 1,
            )
            domain.nginx_config_path = str(conf)
            reload_nginx()

        self.repo.save(domain)
        self._audit(event, domain_id=domain.id, company_id=domain.company_id, user_id=user_id, hostname=domain.hostname)
        return self.status(domain.id, domain.company_id)

    def check_expiring(self, within_days: int = 30) -> List[CompanyDomain]:
        """Return domains needing renewal."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=within_days)
        rows = (
            self.db.query(CompanyDomain)
            .filter(
                CompanyDomain.ssl_status.in_(
                    [SslStatus.ACTIVE.value, SslStatus.ISSUED.value, "issued", "active"]
                ),
                CompanyDomain.ssl_expires_at.isnot(None),
                CompanyDomain.ssl_expires_at <= cutoff,
            )
            .all()
        )
        return rows

    def mark_expired(self) -> int:
        now = datetime.now(timezone.utc)
        rows = (
            self.db.query(CompanyDomain)
            .filter(
                CompanyDomain.ssl_expires_at.isnot(None),
                CompanyDomain.ssl_expires_at <= now,
                CompanyDomain.ssl_status.notin_([SslStatus.EXPIRED.value, SslStatus.NONE.value]),
            )
            .all()
        )
        for d in rows:
            d.ssl_status = SslStatus.EXPIRED.value
            d.ssl_last_checked_at = now
        if rows:
            self.db.commit()
        return len(rows)

    def auto_renew_due(self, max_attempts: int = 5) -> List[Dict[str, Any]]:
        results = []
        self.mark_expired()
        for domain in self.check_expiring(30):
            if int(domain.renew_attempts or 0) >= max_attempts:
                results.append({"hostname": domain.hostname, "skipped": True, "reason": "max_attempts"})
                continue
            try:
                out = self.renew(domain.id, domain.company_id, domain.company_id)
                results.append({"hostname": domain.hostname, "ok": True, "status": out.get("ssl_status")})
            except Exception as exc:
                results.append({"hostname": domain.hostname, "ok": False, "error": str(exc)})
        return results
