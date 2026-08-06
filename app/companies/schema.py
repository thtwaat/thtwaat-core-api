"""
app/companies/schema.py

Pydantic v2 schemas for the Companies module.
Follows strict separation of concerns:
  - Base       : shared fields
  - Create     : input schema for POST
  - Update     : partial input schema for PATCH
  - Response   : output schema (safe — no internal fields leaked)
  - ListResponse: paginated list wrapper
"""

import uuid
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.companies.model import CompanyPlan, CompanyStatus


# ── Shared base ─────────────────────────────────────────────────────────────

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Legal company name")
    display_name: Optional[str] = Field(None, max_length=255, description="Public-facing display name")
    description: Optional[str] = Field(None, max_length=2000)
    website: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    timezone: str = Field(default="UTC", max_length=100)


# ── Create ───────────────────────────────────────────────────────────────────

class CompanyCreate(CompanyBase):
    """Schema used when registering a new Company tenant."""
    slug: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe unique identifier; auto-generated from name when omitted",
    )

    @field_validator("slug")
    @classmethod
    def slug_must_be_lowercase(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        return v.lower().strip()


# ── Update (PATCH — all optional) ───────────────────────────────────────────

class CompanyUpdate(BaseModel):
    """Partial update schema. Only provided fields will be updated."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    website: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=100)
    settings: Optional[dict[str, Any]] = Field(None, description="Tenant-level feature flags")


# ── Admin-only Update ────────────────────────────────────────────────────────

class CompanyAdminUpdate(CompanyUpdate):
    """Extended update schema for platform admins (plan, status, limits)."""
    plan: Optional[CompanyPlan] = None
    status: Optional[CompanyStatus] = None
    is_verified: Optional[bool] = None
    is_active: Optional[bool] = None
    max_users: Optional[int] = Field(None, ge=1, le=10000)
    max_apps: Optional[int] = Field(None, ge=1, le=1000)
    # Usage meter quota overrides (applied via UsageService — not duplicate APIs)
    max_agents: Optional[int] = Field(None, ge=0)
    max_messages: Optional[int] = Field(None, ge=0)
    max_tokens: Optional[int] = Field(None, ge=0)
    max_storage: Optional[int] = Field(None, ge=0)
    max_domains: Optional[int] = Field(None, ge=0)
    max_team_members: Optional[int] = Field(None, ge=0)
    max_api_keys: Optional[int] = Field(None, ge=0)
    max_templates: Optional[int] = Field(None, ge=0)


# ── Response ─────────────────────────────────────────────────────────────────

class CompanyResponse(CompanyBase):
    """Public-safe response schema returned by API endpoints."""
    id: uuid.UUID
    slug: str
    plan: CompanyPlan
    status: CompanyStatus
    is_verified: bool
    is_active: bool
    max_users: int
    max_apps: int
    settings: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


# ── Paginated List Response ──────────────────────────────────────────────────

class CompanyListResponse(BaseModel):
    """Wrapper for paginated company list results."""
    total: int
    page: int
    page_size: int
    results: list[CompanyResponse]
