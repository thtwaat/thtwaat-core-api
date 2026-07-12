"""
app/companies/model.py

SQLAlchemy ORM model for Company.
Designed for Enterprise Multi-Tenant SaaS (similar to Zoho / Microsoft 365).

A Company is the top-level tenant entity. It can own:
  - Multiple Users (via users module)
  - Multiple Apps    (via apps module)
  - Multiple Products (via products/apps module)
"""

import uuid
import enum
from sqlalchemy import (
    Column, String, Boolean, Integer,
    Enum as SAEnum, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin


class CompanyStatus(str, enum.Enum):
    """Lifecycle status of a company tenant."""
    TRIAL      = "trial"       # Newly registered, evaluation period
    ACTIVE     = "active"      # Paying / active tenant
    SUSPENDED  = "suspended"   # Temporarily disabled (e.g. payment failure)
    CANCELLED  = "cancelled"   # Permanently closed account


class CompanyPlan(str, enum.Enum):
    """Subscription tier of the company."""
    FREE       = "free"
    STARTER    = "starter"
    GROWTH     = "growth"
    ENTERPRISE = "enterprise"


class Company(Base, TimestampMixin):
    """
    Represents a tenant organisation on the THTWAAT platform.

    Key design decisions:
    - Uses UUID primary key for security and distributed-system safety.
    - `slug` is the human-readable unique identifier used in URLs (e.g. /companies/acme-corp).
    - `settings` (JSONB) stores tenant-level feature flags & preferences without schema migrations.
    - `max_users` / `max_apps` enforce plan-level limits at the service layer.
    """

    __tablename__ = "companies"

    # ── Identity ────────────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    slug = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # ── Contact / Metadata ──────────────────────────────────────────────────
    website = Column(String(500), nullable=True)
    logo_url = Column(String(500), nullable=True)
    industry = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    timezone = Column(String(100), default="UTC", nullable=False)

    # ── Subscription / Plan ─────────────────────────────────────────────────
    plan = Column(
        SAEnum(CompanyPlan, name="company_plan_enum"),
        default=CompanyPlan.FREE,
        nullable=False,
    )
    status = Column(
        SAEnum(CompanyStatus, name="company_status_enum"),
        default=CompanyStatus.TRIAL,
        nullable=False,
    )

    # ── Resource Limits (enforced by service layer) ─────────────────────────
    max_users = Column(Integer, default=5,   nullable=False)
    max_apps  = Column(Integer, default=1,   nullable=False)

    # ── Feature Flags / Tenant Settings (JSONB) ─────────────────────────────
    # Example: {"ai_enabled": true, "custom_domain": "acme.thtwaat.com"}
    settings = Column(JSONB, default=dict, nullable=False)

    # ── Verification / Security ─────────────────────────────────────────────
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active   = Column(Boolean, default=True,  nullable=False)

    def __repr__(self) -> str:
        return f"<Company id={self.id} slug={self.slug!r} plan={self.plan}>"
