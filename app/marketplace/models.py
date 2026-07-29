"""Marketplace Template ORM models — registry, versions, installations."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class TemplateCategory(str, enum.Enum):
    WEBSITE = "website"
    LANDING = "landing"
    SAAS = "saas"
    CRM = "crm"
    HELPDESK = "helpdesk"
    ECOMMERCE = "ecommerce"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    REAL_ESTATE = "real_estate"
    RESTAURANT = "restaurant"
    FINANCE = "finance"
    LEGAL = "legal"


class TemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class InstallStatus(str, enum.Enum):
    PENDING = "pending"
    CONNECTING = "connecting"
    READY = "ready"
    PUBLISHED = "published"
    UPDATE_AVAILABLE = "update_available"
    FAILED = "failed"
    UNINSTALLED = "uninstalled"


class MarketplaceTemplate(Base, TimestampMixin):
    """Catalog entry in the Template Registry / Marketplace."""

    __tablename__ = "marketplace_templates"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_marketplace_templates_slug"),
        Index("ix_marketplace_templates_category_status", "category", "status"),
        Index("ix_marketplace_templates_featured", "is_featured", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    slug = Column(String(120), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(
        SAEnum(
            TemplateCategory,
            name="template_category_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    industry = Column(String(120), nullable=True)
    description = Column(Text, nullable=False, default="")
    version = Column(String(32), nullable=False, default="1.0.0")
    thumbnail = Column(String(500), nullable=True)
    icon = Column(String(120), nullable=True)
    tags = Column(ARRAY(String), nullable=False, default=list)
    author = Column(String(160), nullable=False, default="THTWAAT")
    status = Column(
        SAEnum(
            TemplateStatus,
            name="template_status_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TemplateStatus.DRAFT,
        index=True,
    )
    price = Column(Numeric(12, 2), nullable=False, default=0)
    is_public = Column(Boolean, nullable=False, default=True)
    is_featured = Column(Boolean, nullable=False, default=False)
    supports_agents = Column(Boolean, nullable=False, default=True)
    supports_domains = Column(Boolean, nullable=False, default=True)
    supports_billing = Column(Boolean, nullable=False, default=False)
    supports_mobile = Column(Boolean, nullable=False, default=False)
    package_path = Column(String(255), nullable=True)  # e.g. apps/templates/landing
    install_count = Column(Integer, nullable=False, default=0)
    default_config = Column(JSONB, nullable=False, default=dict)

    versions = relationship(
        "TemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateVersion.created_at.desc()",
    )
    installations = relationship("TemplateInstallation", back_populates="template")


class TemplateVersion(Base, TimestampMixin):
    """Immutable version snapshot for a marketplace template."""

    __tablename__ = "marketplace_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_template_version"),
        Index("ix_template_versions_template", "template_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(String(32), nullable=False)
    changelog = Column(Text, nullable=True)
    config = Column(JSONB, nullable=False, default=dict)
    is_latest = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)

    template = relationship("MarketplaceTemplate", back_populates="versions")


class TemplateInstallation(Base, TimestampMixin):
    """A company's installed instance of a marketplace template."""

    __tablename__ = "marketplace_template_installations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "template_id",
            name="uq_company_template_install",
        ),
        Index("ix_template_installs_company_status", "company_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_template_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    installed_version = Column(String(32), nullable=False)
    previous_version = Column(String(32), nullable=True)
    previous_config = Column(JSONB, nullable=True)
    config = Column(JSONB, nullable=False, default=dict)
    status = Column(
        SAEnum(
            InstallStatus,
            name="template_install_status_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=InstallStatus.PENDING,
        index=True,
    )
    agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    api_key_id = Column(UUID(as_uuid=True), nullable=True)
    api_key_prefix = Column(String(32), nullable=True)
    domain_id = Column(UUID(as_uuid=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    update_available = Column(Boolean, nullable=False, default=False)
    latest_available_version = Column(String(32), nullable=True)
    failure_reason = Column(Text, nullable=True)
    installed_by = Column(UUID(as_uuid=True), nullable=True)

    template = relationship("MarketplaceTemplate", back_populates="installations")
    version = relationship("TemplateVersion")
