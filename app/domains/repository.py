"""Domain Manager repository."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.models import CompanyDomain, DomainStatus


class DomainRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, domain: CompanyDomain) -> CompanyDomain:
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        return domain

    def save(self, domain: CompanyDomain) -> CompanyDomain:
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        return domain

    def get_by_id(self, domain_id: UUID) -> Optional[CompanyDomain]:
        return self.db.query(CompanyDomain).filter(CompanyDomain.id == domain_id).first()

    def get_for_company(self, domain_id: UUID, company_id: UUID) -> Optional[CompanyDomain]:
        return (
            self.db.query(CompanyDomain)
            .filter(
                CompanyDomain.id == domain_id,
                CompanyDomain.company_id == company_id,
            )
            .first()
        )

    def get_by_hostname(self, hostname: str) -> Optional[CompanyDomain]:
        return (
            self.db.query(CompanyDomain)
            .filter(CompanyDomain.hostname == hostname.lower())
            .first()
        )

    def list_for_company(self, company_id: UUID) -> List[CompanyDomain]:
        return (
            self.db.query(CompanyDomain)
            .filter(CompanyDomain.company_id == company_id)
            .order_by(CompanyDomain.created_at.desc())
            .all()
        )

    def count_for_company(self, company_id: UUID) -> int:
        return (
            self.db.query(CompanyDomain)
            .filter(CompanyDomain.company_id == company_id)
            .count()
        )

    def delete(self, domain: CompanyDomain) -> None:
        self.db.delete(domain)
        self.db.commit()

    def clear_primary(self, company_id: UUID) -> None:
        (
            self.db.query(CompanyDomain)
            .filter(CompanyDomain.company_id == company_id, CompanyDomain.is_primary.is_(True))
            .update({"is_primary": False})
        )
        self.db.commit()

    def list_active_for_progress(self) -> List[CompanyDomain]:
        """Platform-wide (all companies) domains still moving toward LIVE.

        Used by the scheduler to drive automatic DNS verification and SSL
        issuance — mirrors list_cors_origins() in being an all-tenant scan.
        """
        return (
            self.db.query(CompanyDomain)
            .filter(
                CompanyDomain.status.in_(
                    [
                        DomainStatus.PENDING,
                        DomainStatus.DNS_PENDING,
                        DomainStatus.VERIFIED,
                        DomainStatus.SSL_PENDING,
                    ]
                )
            )
            .order_by(CompanyDomain.updated_at.asc())
            .all()
        )

    def list_cors_origins(self) -> List[str]:
        rows = (
            self.db.query(CompanyDomain.cors_origin)
            .filter(
                CompanyDomain.status.in_(
                    [
                        DomainStatus.VERIFIED,
                        DomainStatus.SSL_PENDING,
                        DomainStatus.LIVE,
                    ]
                )
            )
            .all()
        )
        return [r[0] for r in rows if r[0]]
