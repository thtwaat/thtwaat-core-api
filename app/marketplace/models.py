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
    # Phase 1 catalog expansion (prompt / vertical packs)
    WRITING = "writing"
    CODING = "coding"
    MARKETING = "marketing"
    HR = "hr"
    RESEARCH = "research"
    AI_AGENTS = "ai_agents"
    BUSINESS = "business"
    ANALYTICS = "analytics"
    # Store Home verticals (additive)
    INSURANCE = "insurance"
    GOVERNMENT = "government"
    TRAVEL = "travel"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    SALES = "sales"
    ERP = "erp"
    BI = "bi"
    DEVOPS = "devops"
    SECURITY = "security"
    NEWS = "news"
    MEDIA = "media"
    STARTUP = "startup"
    PRODUCTIVITY = "productivity"
    AUTOMATION = "automation"
    MULTILINGUAL = "multilingual"


class TemplateKind(str, enum.Enum):
    PACKAGE = "package"
    PROMPT = "prompt"
    AGENT = "agent"


class PricingTier(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


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
        Index("ix_marketplace_templates_kind_status", "kind", "status"),
        Index("ix_marketplace_templates_tags_gin", "tags", postgresql_using="gin"),
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
    kind = Column(
        SAEnum(
            TemplateKind,
            name="template_kind_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TemplateKind.PACKAGE,
        index=True,
    )
    pricing_tier = Column(
        SAEnum(
            PricingTier,
            name="template_pricing_tier_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PricingTier.FREE,
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
    # Store Home media / trust enrichment (additive, null-safe)
    banner_url = Column(String(500), nullable=True)
    screenshots = Column(ARRAY(String), nullable=False, default=list)
    video_url = Column(String(500), nullable=True)
    live_demo_url = Column(String(500), nullable=True)
    discount_percent = Column(Integer, nullable=True)
    estimated_install_minutes = Column(Integer, nullable=True)
    compatibility = Column(String(255), nullable=True)
    is_editors_choice = Column(Boolean, nullable=False, default=False)

    versions = relationship(
        "TemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateVersion.created_at.desc()",
    )
    installations = relationship("TemplateInstallation", back_populates="template")
    favorites = relationship("TemplateFavorite", back_populates="template", cascade="all, delete-orphan")


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


class TemplateFavorite(Base, TimestampMixin):
    """Per-user favorite of a marketplace template (tenant-scoped)."""

    __tablename__ = "marketplace_template_favorites"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "user_id",
            "template_id",
            name="uq_marketplace_favorite_company_user_template",
        ),
        Index("ix_marketplace_favorites_user", "company_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    template = relationship("MarketplaceTemplate", back_populates="favorites")


class MarketplaceCategoryMeta(Base, TimestampMixin):
    """Optional per-category icon/featured/popularity without enum churn."""

    __tablename__ = "marketplace_category_meta"

    category_slug = Column(String(64), primary_key=True)
    display_name = Column(String(120), nullable=True)
    icon = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)
    is_featured = Column(Boolean, nullable=False, default=False)
    popularity_score = Column(Integer, nullable=False, default=0)
    display_order = Column(Integer, nullable=False, default=100)


class MarketplaceCollection(Base, TimestampMixin):
    """Curated or computed storefront collection (rail / strip)."""

    __tablename__ = "marketplace_collections"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_marketplace_collections_slug"),
        Index("ix_marketplace_collections_featured", "is_featured", "is_public"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    slug = Column(String(120), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    icon = Column(String(120), nullable=True)
    banner_url = Column(String(500), nullable=True)
    is_public = Column(Boolean, nullable=False, default=True)
    is_featured = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=100)
    collection_type = Column(String(32), nullable=False, default="curated")  # curated | computed
    computed_rule = Column(JSONB, nullable=False, default=dict)

    items = relationship(
        "MarketplaceCollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="MarketplaceCollectionItem.position",
    )


class MarketplaceCollectionItem(Base, TimestampMixin):
    __tablename__ = "marketplace_collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "template_id", name="uq_marketplace_collection_template"),
        Index("ix_marketplace_collection_items_order", "collection_id", "position"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    collection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    position = Column(Integer, nullable=False, default=0)

    collection = relationship("MarketplaceCollection", back_populates="items")
    template = relationship("MarketplaceTemplate")


class MarketplaceTemplateEvent(Base, TimestampMixin):
    """Lightweight discovery events (recently viewed, etc.)."""

    __tablename__ = "marketplace_template_events"
    __table_args__ = (
        Index(
            "ix_marketplace_template_events_user_type",
            "company_id",
            "user_id",
            "event_type",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(32), nullable=False, default="view")
