"""Pydantic schemas for AI Agent Store."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent_store.models import (
    AbuseReportStatus,
    ListingStatus,
    PricingModel,
    PublisherStatus,
    PurchaseStatus,
)


# ── Publisher ─────────────────────────────────────────────────────────────────

class PublisherUpsert(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    bio: Optional[str] = None
    website: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    banner_url: Optional[str] = Field(None, max_length=500)
    github_url: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    twitter_url: Optional[str] = Field(None, max_length=500)


class PublisherResponse(BaseModel):
    id: UUID
    company_id: UUID
    display_name: str
    slug: str
    bio: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    is_verified: bool
    status: PublisherStatus
    revenue_share_bps: int
    created_at: datetime
    # Additive public profile aggregates (optional for private endpoints)
    templates_count: Optional[int] = None
    published_count: Optional[int] = None
    average_rating: Optional[float] = None
    total_installs: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PublisherPublicProfile(BaseModel):
    """Public publisher page — additive, no private company fields."""

    id: UUID
    display_name: str
    slug: str
    bio: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    is_verified: bool
    followers_count: int = 0
    following_count: int = 0
    templates_count: int = 0
    published_count: int = 0
    average_rating: float = 0.0
    total_installs: int = 0
    listings: List["ListingResponse"] = Field(default_factory=list)


# ── Listings ──────────────────────────────────────────────────────────────────

class ListingCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    short_description: str = Field("", max_length=500)
    long_description: str = ""
    screenshots: List[str] = Field(default_factory=list, max_length=20)
    demo_url: Optional[str] = None
    cover_url: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    supported_languages: List[str] = Field(default_factory=lambda: ["en"])
    knowledge_requirements: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    pricing_model: PricingModel = PricingModel.FREE
    price_amount: Decimal = Decimal("0")
    currency: str = Field("USD", min_length=3, max_length=3)
    pricing_tier: Optional[str] = Field(
        None,
        description="UI badge: free|pro|enterprise — stored in default_config.store.pricing_tier",
    )
    source_agent_id: Optional[UUID] = None
    marketplace_category: str = Field(
        default="helpdesk",
        description="Underlying MarketplaceTemplate category for install reuse",
    )
    default_config: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    release_notes: Optional[str] = "Initial release"
    submit_for_review: bool = False
    as_private: bool = False

    @field_validator("price_amount")
    @classmethod
    def non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("price_amount must be >= 0")
        return v


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    short_description: Optional[str] = Field(None, max_length=500)
    long_description: Optional[str] = None
    screenshots: Optional[List[str]] = None
    demo_url: Optional[str] = None
    cover_url: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    supported_languages: Optional[List[str]] = None
    knowledge_requirements: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    pricing_model: Optional[PricingModel] = None
    price_amount: Optional[Decimal] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    source_agent_id: Optional[UUID] = None
    release_notes: Optional[str] = None
    default_config: Optional[Dict[str, Any]] = None


class ListingStatusUpdate(BaseModel):
    status: ListingStatus = Field(
        ...,
        description="Publisher-controlled: draft|private|archived (submit uses /submit)",
    )


class ListingVersionCreate(BaseModel):
    version: str = Field(..., min_length=1, max_length=32)
    release_notes: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class ListingResponse(BaseModel):
    id: UUID
    publisher_id: UUID
    publisher_name: Optional[str] = None
    publisher_verified: bool = False
    template_id: UUID
    source_agent_id: Optional[UUID] = None
    slug: str
    title: str
    short_description: str
    long_description: str
    screenshots: List[str] = Field(default_factory=list)
    demo_url: Optional[str] = None
    cover_url: Optional[str] = None
    logo_url: Optional[str] = None
    supported_languages: List[str] = Field(default_factory=list)
    knowledge_requirements: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    pricing_model: PricingModel
    price_amount: Decimal
    currency: str
    status: ListingStatus
    is_featured: bool
    is_verified_badge: bool
    install_count: int
    download_count: int
    rating_avg: Decimal
    rating_count: int
    current_version: str
    release_notes: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    installed: bool = False
    purchased: bool = False

    model_config = ConfigDict(from_attributes=True)


class StorefrontResponse(BaseModel):
    featured: List[ListingResponse] = Field(default_factory=list)
    trending: List[ListingResponse] = Field(default_factory=list)
    top_rated: List[ListingResponse] = Field(default_factory=list)
    most_installed: List[ListingResponse] = Field(default_factory=list)
    newest: List[ListingResponse] = Field(default_factory=list)
    recently_updated: List[ListingResponse] = Field(default_factory=list)
    categories: List[Dict[str, Any]] = Field(default_factory=list)


class ListingDetailResponse(BaseModel):
    listing: ListingResponse
    versions: List[Dict[str, Any]] = Field(default_factory=list)
    reviews: List["ReviewResponse"] = Field(default_factory=list)
    related: List[ListingResponse] = Field(default_factory=list)
    recommendations: List[ListingResponse] = Field(default_factory=list)


# ── Install / purchase ────────────────────────────────────────────────────────

class StoreInstallRequest(BaseModel):
    agent_id: Optional[UUID] = None
    create_api_key: bool = True
    config_overrides: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[str] = None
    # Paid listings
    gateway: str = "manual"
    payment_method: str = "card"
    publish_agent: bool = False


class StoreInstallResponse(BaseModel):
    listing_id: UUID
    installation_id: UUID
    purchase_id: Optional[UUID] = None
    payment_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    status: str
    publish_status: Optional[str] = None


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    body: Optional[str] = None


class ReviewResponse(BaseModel):
    id: UUID
    listing_id: UUID
    company_id: UUID
    user_id: UUID
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    publisher_reply: Optional[str] = None
    publisher_replied_at: Optional[datetime] = None
    helpful_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewReplyRequest(BaseModel):
    reply: str = Field(..., min_length=1, max_length=5000)


class PublisherAiGenerateRequest(BaseModel):
    kind: str = Field(
        ...,
        pattern="^(summary|tags|documentation|screenshots_description|seo_description)$",
    )
    title: str = Field(..., min_length=1, max_length=255)
    short_description: str = ""
    long_description: str = ""
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    language: str = "en"


class PublisherAiGenerateResponse(BaseModel):
    kind: str
    result: str
    tags: List[str] = Field(default_factory=list)


# ── Analytics / revenue ───────────────────────────────────────────────────────

class PublisherAnalytics(BaseModel):
    listings: int
    published_listings: int
    draft_listings: int = 0
    pending_review_listings: int = 0
    private_listings: int = 0
    rejected_listings: int = 0
    archived_listings: int = 0
    total_installs: int
    active_installs: int = 0
    total_downloads: int
    average_rating: float
    review_count: int
    completed_purchases: int
    gross_revenue: float
    publisher_revenue: float
    platform_fees: float
    monthly_growth_pct: float = 0.0
    currency: str = "USD"
    # Timeseries / breakdown (additive)
    daily_installs: List[Dict[str, Any]] = Field(default_factory=list)
    monthly_installs: List[Dict[str, Any]] = Field(default_factory=list)
    countries: List[Dict[str, Any]] = Field(default_factory=list)
    devices: List[Dict[str, Any]] = Field(default_factory=list)
    conversion_rate: float = 0.0
    retention_rate: float = 0.0


class StoreAdminStats(BaseModel):
    listings_total: int
    pending_review: int
    published: int
    suspended: int
    open_abuse_reports: int
    purchases_completed: int
    gross_gmv: float


# ── Moderation ────────────────────────────────────────────────────────────────

class ModerateListingRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|suspend|feature|unfeature|verify)$")
    notes: Optional[str] = None


class AbuseReportCreate(BaseModel):
    reason: str = Field(..., min_length=2, max_length=100)
    details: Optional[str] = None


class AbuseReportResponse(BaseModel):
    id: UUID
    listing_id: UUID
    reason: str
    details: Optional[str] = None
    status: AbuseReportStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AbuseResolveRequest(BaseModel):
    status: AbuseReportStatus
    resolution_notes: Optional[str] = None


ListingDetailResponse.model_rebuild()
PublisherPublicProfile.model_rebuild()
