"""ORM models for the AI Agent Store (wraps MarketplaceTemplate for install reuse)."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin


class PublisherStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


class ListingStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class PricingModel(str, enum.Enum):
    FREE = "free"
    ONE_TIME = "one_time"
    SUBSCRIPTION = "subscription"


class PurchaseStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"
    FAILED = "failed"


class AbuseReportStatus(str, enum.Enum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AgentStorePublisher(Base, TimestampMixin):
    __tablename__ = "agent_store_publishers"
    __table_args__ = (UniqueConstraint("company_id", name="uq_agent_store_publisher_company"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name = Column(String(255), nullable=False)
    slug = Column(String(120), unique=True, nullable=False, index=True)
    bio = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    logo_url = Column(String(500), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    status = Column(
        SAEnum(
            PublisherStatus,
            name="agent_store_publisher_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PublisherStatus.ACTIVE,
    )
    payout_metadata = Column(JSONB, nullable=False, default=dict)
    revenue_share_bps = Column(Integer, nullable=False, default=7000)  # publisher share 70%


class AgentStoreListing(Base, TimestampMixin):
    __tablename__ = "agent_store_listings"
    __table_args__ = (
        Index("ix_agent_store_listings_status_featured", "status", "is_featured"),
        Index("ix_agent_store_listings_trending", "install_count", "rating_avg"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publisher_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_store_publishers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Install engine — required for MarketplaceService.install reuse
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_templates.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    slug = Column(String(120), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    short_description = Column(String(500), nullable=False, default="")
    long_description = Column(Text, nullable=False, default="")
    screenshots = Column(JSONB, nullable=False, default=list)
    demo_url = Column(String(500), nullable=True)
    supported_languages = Column(JSONB, nullable=False, default=list)
    knowledge_requirements = Column(Text, nullable=True)
    categories = Column(JSONB, nullable=False, default=list)
    tags = Column(JSONB, nullable=False, default=list)

    pricing_model = Column(
        SAEnum(
            PricingModel,
            name="agent_store_pricing_model_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PricingModel.FREE,
    )
    price_amount = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")

    status = Column(
        SAEnum(
            ListingStatus,
            name="agent_store_listing_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ListingStatus.DRAFT,
    )
    is_featured = Column(Boolean, nullable=False, default=False)
    is_verified_badge = Column(Boolean, nullable=False, default=False)

    install_count = Column(Integer, nullable=False, default=0)
    download_count = Column(Integer, nullable=False, default=0)
    rating_avg = Column(Numeric(3, 2), nullable=False, default=0)
    rating_count = Column(Integer, nullable=False, default=0)

    current_version = Column(String(32), nullable=False, default="1.0.0")
    release_notes = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    moderated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderation_notes = Column(Text, nullable=True)


class AgentStoreReview(Base, TimestampMixin):
    __tablename__ = "agent_store_reviews"
    __table_args__ = (
        UniqueConstraint("listing_id", "company_id", "user_id", name="uq_agent_store_review"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_store_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1..5
    title = Column(String(200), nullable=True)
    body = Column(Text, nullable=True)
    is_visible = Column(Boolean, nullable=False, default=True)


class AgentStorePurchase(Base, TimestampMixin):
    __tablename__ = "agent_store_purchases"
    __table_args__ = (
        Index("ix_agent_store_purchases_buyer", "buyer_company_id"),
        Index("ix_agent_store_purchases_listing", "listing_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_store_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    buyer_company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    buyer_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payment_id = Column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    installation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_template_installations.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    publisher_share = Column(Numeric(12, 2), nullable=False, default=0)
    platform_share = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(
        SAEnum(
            PurchaseStatus,
            name="agent_store_purchase_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PurchaseStatus.PENDING,
    )
    pricing_model = Column(String(32), nullable=False, default="free")
    meta = Column("metadata", JSONB, nullable=False, default=dict)


class AgentStoreAbuseReport(Base, TimestampMixin):
    __tablename__ = "agent_store_abuse_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_store_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    reporter_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    status = Column(
        SAEnum(
            AbuseReportStatus,
            name="agent_store_abuse_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AbuseReportStatus.OPEN,
    )
    resolution_notes = Column(Text, nullable=True)
