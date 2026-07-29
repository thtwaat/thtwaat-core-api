"""Pydantic schemas for Domain Manager APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DnsRecord(BaseModel):
    type: str  # TXT | CNAME | A | AAAA
    host: str
    value: str
    ttl: int = 300
    purpose: str = "verification"


class DomainCreate(BaseModel):
    hostname: str = Field(..., min_length=3, max_length=253, examples=["chat.acme.com"])
    verification_method: str = Field(default="TXT", pattern="^(TXT|CNAME)$")
    agent_id: Optional[UUID] = None
    widget_id: Optional[str] = Field(default=None, max_length=64)
    is_primary: bool = False

    @field_validator("hostname")
    @classmethod
    def normalize_hostname(cls, v: str) -> str:
        host = v.strip().lower().rstrip(".")
        if "://" in host:
            raise ValueError("hostname must not include protocol (https://)")
        if "/" in host or " " in host:
            raise ValueError("hostname must be a bare domain (e.g. chat.company.com)")
        if not any(c.isalpha() for c in host):
            raise ValueError("invalid hostname")
        return host


class DomainUpdate(BaseModel):
    agent_id: Optional[UUID] = None
    widget_id: Optional[str] = Field(default=None, max_length=64)
    is_primary: Optional[bool] = None
    verification_method: Optional[str] = Field(default=None, pattern="^(TXT|CNAME)$")


class DomainResponse(BaseModel):
    id: UUID
    company_id: UUID
    hostname: str
    status: str
    verification_method: str
    verification_token: str
    verified_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    agent_id: Optional[UUID] = None
    widget_id: Optional[str] = None
    is_primary: bool
    dns_records: List[Dict[str, Any]] = Field(default_factory=list)
    ssl_status: str
    ssl_issued_at: Optional[datetime] = None
    ssl_expires_at: Optional[datetime] = None
    ssl_renewal_at: Optional[datetime] = None
    ssl_provider: Optional[str] = None
    ssl_challenge: Optional[str] = "http-01"
    certificate_serial: Optional[str] = None
    renew_attempts: int = 0
    renewal_error: Optional[str] = None
    cors_origin: str
    widget_urls: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DomainVerifyResponse(BaseModel):
    id: UUID
    hostname: str
    status: str
    verified: bool
    message: str
    dns_records: List[Dict[str, Any]] = Field(default_factory=list)
    failure_reason: Optional[str] = None


class DomainDashboardItem(BaseModel):
    id: UUID
    hostname: str
    status: str
    ssl_status: str
    verification_method: str
    is_primary: bool
    dns_records: List[Dict[str, Any]]
    widget_urls: Dict[str, str]
    cors_origin: str
    failure_reason: Optional[str] = None
    verified_at: Optional[datetime] = None
    ssl_expires_at: Optional[datetime] = None


class DomainDashboardResponse(BaseModel):
    company_id: UUID
    domains: List[DomainDashboardItem]
    allowed_origins: List[str]
    max_domains: int
    domains_used: int
    instructions: Dict[str, str]


class SslRequestResponse(BaseModel):
    id: UUID
    hostname: str
    status: str
    ssl_status: str
    message: str
