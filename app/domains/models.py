"""Company custom domain ORM model."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Integer,
    Enum as SAEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin


class DomainStatus(str, enum.Enum):
    PENDING = "PENDING"
    DNS_PENDING = "DNS_PENDING"
    VERIFIED = "VERIFIED"
    SSL_PENDING = "SSL_PENDING"
    LIVE = "LIVE"
    FAILED = "FAILED"


class DomainVerificationMethod(str, enum.Enum):
    TXT = "TXT"
    CNAME = "CNAME"


class SslStatus(str, enum.Enum):
    """Certificate lifecycle (uppercase canonical; legacy lowercase mapped in service)."""

    NONE = "NONE"
    PENDING = "PENDING"
    REQUESTING = "REQUESTING"
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    RENEWING = "RENEWING"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class SslChallengeType(str, enum.Enum):
    HTTP_01 = "http-01"
    DNS_01 = "dns-01"  # future-ready / wildcard


class CompanyDomain(Base, TimestampMixin):
    """Custom domain owned by a company (multi-tenant isolated)."""

    __tablename__ = "company_domains"
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_company_domains_hostname"),
        Index("ix_company_domains_company_status", "company_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    hostname = Column(String(253), nullable=False)  # e.g. chat.company.com
    status = Column(
        SAEnum(
            DomainStatus,
            name="domain_status_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DomainStatus.PENDING,
        index=True,
    )

    # Ownership verification
    verification_method = Column(
        SAEnum(
            DomainVerificationMethod,
            name="domain_verification_method_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DomainVerificationMethod.TXT,
    )
    verification_token = Column(String(128), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)

    # Binding
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    widget_id = Column(String(64), nullable=True, index=True)
    is_primary = Column(Boolean, nullable=False, default=False)

    # DNS instructions snapshot
    dns_records = Column(JSONB, nullable=False, default=list)

    # SSL / Let's Encrypt
    ssl_status = Column(String(32), nullable=False, default=SslStatus.NONE.value)
    ssl_issued_at = Column(DateTime(timezone=True), nullable=True)
    ssl_expires_at = Column(DateTime(timezone=True), nullable=True)
    ssl_renewal_at = Column(DateTime(timezone=True), nullable=True)
    ssl_provider = Column(String(64), nullable=True, default="letsencrypt")
    ssl_challenge = Column(String(32), nullable=False, default=SslChallengeType.HTTP_01.value)
    certificate_serial = Column(String(128), nullable=True)
    ssl_last_checked_at = Column(DateTime(timezone=True), nullable=True)
    renew_attempts = Column(Integer, nullable=False, default=0)
    renewal_error = Column(Text, nullable=True)
    cert_path = Column(String(500), nullable=True)
    key_path = Column(String(500), nullable=True)
    nginx_config_path = Column(String(500), nullable=True)
    is_wildcard = Column(Boolean, nullable=False, default=False)

    # Derived CORS origin (https://hostname)
    cors_origin = Column(String(300), nullable=False)
