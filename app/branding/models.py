"""ORM models for company white-label branding and versioned assets."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin


class BrandingAssetType(str, enum.Enum):
    LOGO = "logo"
    DARK_LOGO = "dark_logo"
    FAVICON = "favicon"
    SPLASH = "splash"
    LAUNCHER_ICON = "launcher_icon"
    EMAIL_LOGO = "email_logo"
    LOGIN_BACKGROUND = "login_background"
    WIDGET_LAUNCHER = "widget_launcher"
    WIDGET_HEADER = "widget_header"


class CompanyBranding(Base, TimestampMixin):
    """Per-company white-label configuration (draft + published snapshot)."""

    __tablename__ = "company_branding"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_branding_company_id"),
        Index("ix_company_branding_company_id", "company_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Brand identity ──────────────────────────────────────────────────────
    company_name = Column(String(255), nullable=True)
    copyright_text = Column(String(500), nullable=True)
    footer_text = Column(Text, nullable=True)

    # ── Colors & typography ─────────────────────────────────────────────────
    primary_color = Column(String(32), nullable=False, default="#0F766E")
    secondary_color = Column(String(32), nullable=False, default="#134E4A")
    accent_color = Column(String(32), nullable=False, default="#F59E0B")
    font_family = Column(String(255), nullable=False, default="Inter, system-ui, sans-serif")
    heading_font = Column(String(255), nullable=True)
    dashboard_theme = Column(String(32), nullable=False, default="system")  # light|dark|system
    login_background_url = Column(String(1024), nullable=True)

    # ── Core assets ─────────────────────────────────────────────────────────
    logo_url = Column(String(1024), nullable=True)
    dark_logo_url = Column(String(1024), nullable=True)
    favicon_url = Column(String(1024), nullable=True)

    # ── Nested branding blocks (JSONB) ──────────────────────────────────────
    # email: sender_name, sender_email, logo_url, templates{welcome,password_reset,invoice,notification}
    email = Column(JSONB, nullable=False, default=dict)
    # mobile: app_name, android_package, ios_bundle_id, splash_url, launcher_icon_url, colors
    mobile = Column(JSONB, nullable=False, default=dict)
    # widget defaults cascaded into PublishService WidgetConfig
    widget = Column(JSONB, nullable=False, default=dict)
    # hostname roles — actual DNS/SSL owned by DomainService
    domain_roles = Column(JSONB, nullable=False, default=dict)

    # ── Publish / versioning (zero-downtime swap via published_snapshot) ─────
    draft_version = Column(Integer, nullable=False, default=1)
    published_version = Column(Integer, nullable=False, default=0)
    published_snapshot = Column(JSONB, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    is_published = Column(Boolean, nullable=False, default=False)


class BrandingAsset(Base, TimestampMixin):
    """Versioned brand asset backed by StorageFile (no file I/O duplication)."""

    __tablename__ = "branding_assets"
    __table_args__ = (
        Index("ix_branding_assets_company_type", "company_id", "asset_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branding.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_type = Column(
        SAEnum(
            BrandingAssetType,
            name="branding_asset_type_enum",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    storage_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("storage_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    url = Column(String(1024), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    checksum = Column(String(64), nullable=True)
