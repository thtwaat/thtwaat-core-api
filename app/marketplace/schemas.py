"""Pydantic schemas for Template Registry + Marketplace."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(..., min_length=2, max_length=200)
    category: str
    kind: str = "package"
    pricing_tier: str = "free"
    industry: Optional[str] = None
    description: str = ""
    version: str = "1.0.0"
    thumbnail: Optional[str] = None
    icon: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    author: str = "THTWAAT"
    price: Decimal = Decimal("0")
    is_public: bool = True
    is_featured: bool = False
    supports_agents: bool = True
    supports_domains: bool = True
    supports_billing: bool = False
    supports_mobile: bool = False
    package_path: Optional[str] = None
    default_config: Dict[str, Any] = Field(default_factory=dict)
    changelog: Optional[str] = "Initial release"
    publish: bool = False
    banner_url: Optional[str] = None
    screenshots: List[str] = Field(default_factory=list)
    video_url: Optional[str] = None
    live_demo_url: Optional[str] = None
    discount_percent: Optional[int] = Field(default=None, ge=0, le=100)
    estimated_install_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    compatibility: Optional[str] = None
    is_editors_choice: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    kind: Optional[str] = None
    pricing_tier: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    price: Optional[Decimal] = None
    is_public: Optional[bool] = None
    is_featured: Optional[bool] = None
    supports_agents: Optional[bool] = None
    supports_domains: Optional[bool] = None
    supports_billing: Optional[bool] = None
    supports_mobile: Optional[bool] = None
    package_path: Optional[str] = None
    default_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    banner_url: Optional[str] = None
    screenshots: Optional[List[str]] = None
    video_url: Optional[str] = None
    live_demo_url: Optional[str] = None
    discount_percent: Optional[int] = Field(default=None, ge=0, le=100)
    estimated_install_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    compatibility: Optional[str] = None
    is_editors_choice: Optional[bool] = None


class TemplateVersionCreate(BaseModel):
    version: str = Field(..., min_length=1, max_length=32)
    changelog: Optional[str] = None
    release_notes: Optional[str] = Field(
        default=None,
        description="Preferred alias for changelog / release notes body",
    )
    config: Dict[str, Any] = Field(default_factory=dict)
    set_latest: bool = True

    def notes(self) -> Optional[str]:
        return self.release_notes if self.release_notes is not None else self.changelog


class TemplateVersionUpdate(BaseModel):
    """Edit release notes / config; optionally promote to latest."""

    changelog: Optional[str] = None
    release_notes: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    set_latest: bool = False

    def notes(self) -> Optional[str]:
        if self.release_notes is not None:
            return self.release_notes
        return self.changelog


class TemplateResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    category: str
    kind: str = "package"
    pricing_tier: str = "free"
    industry: Optional[str] = None
    description: str
    version: str
    thumbnail: Optional[str] = None
    icon: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    author: str
    status: str
    price: Decimal
    is_public: bool
    is_featured: bool = False
    supports_agents: bool
    supports_domains: bool
    supports_billing: bool
    supports_mobile: bool
    package_path: Optional[str] = None
    install_count: int = 0
    default_config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    installed: bool = False
    update_available: bool = False
    is_favorited: bool = False
    # Store Home enrichment (additive / null-safe)
    banner_url: Optional[str] = None
    screenshots: List[str] = Field(default_factory=list)
    video_url: Optional[str] = None
    live_demo_url: Optional[str] = None
    verified_publisher: Optional[bool] = None
    publisher_slug: Optional[str] = None
    company_name: Optional[str] = None
    discount_percent: Optional[int] = None
    rating_avg: Optional[float] = None
    review_count: Optional[int] = None
    download_count: Optional[int] = None
    estimated_install_minutes: Optional[int] = None
    compatibility: Optional[str] = None
    is_editors_choice: bool = False
    pricing_badge: Optional[str] = None
    # Phase 3 detail enrichment (additive / null-safe)
    listing_id: Optional[UUID] = None
    what_it_does: Optional[str] = None
    best_for: List[str] = Field(default_factory=list)
    use_cases: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    license: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    feature_cards: List[Dict[str, str]] = Field(default_factory=list)
    docs_markdown: Optional[str] = None
    quick_start: Optional[str] = None
    installation_docs: Optional[str] = None
    configuration_docs: Optional[str] = None
    examples_docs: Optional[str] = None
    support_url: Optional[str] = None
    website_url: Optional[str] = None
    docs_url: Optional[str] = None
    min_platform_version: Optional[str] = None
    supported_providers: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    publisher_bio: Optional[str] = None
    publisher_website: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TemplateReviewItem(BaseModel):
    id: UUID
    listing_id: UUID
    company_id: UUID
    user_id: UUID
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    created_at: datetime
    verified_install: bool = False
    helpful_count: int = 0


class TemplateReviewsResponse(BaseModel):
    template_id: UUID
    listing_id: Optional[UUID] = None
    rating_avg: Optional[float] = None
    review_count: int = 0
    distribution: Dict[str, int] = Field(default_factory=dict)
    items: List[TemplateReviewItem] = Field(default_factory=list)


class TemplateVersionResponse(BaseModel):
    id: UUID
    template_id: UUID
    version: str
    changelog: Optional[str] = None
    release_notes: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    is_latest: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_version(cls, version: Any) -> "TemplateVersionResponse":
        base = cls.model_validate(version)
        return base.model_copy(update={"release_notes": base.changelog})


class InstallActionRequest(BaseModel):
    """Phase 2 convenience body for update/uninstall aliases."""
    installation_id: UUID
    version: Optional[str] = None


class InstallRequest(BaseModel):
    version: Optional[str] = None
    agent_id: Optional[UUID] = None
    create_api_key: bool = True
    api_key_name: Optional[str] = "Template install key"
    config_overrides: Dict[str, Any] = Field(default_factory=dict)


class ConnectRequest(BaseModel):
    agent_id: Optional[UUID] = None
    create_api_key: bool = True
    api_key_name: Optional[str] = "Template install key"
    domain_id: Optional[UUID] = None


class InstallationResponse(BaseModel):
    id: UUID
    company_id: UUID
    template_id: UUID
    template_slug: Optional[str] = None
    template_name: Optional[str] = None
    category: Optional[str] = None
    version_id: Optional[UUID] = None
    installed_version: str
    previous_version: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str
    agent_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    api_key_prefix: Optional[str] = None
    api_key: Optional[str] = None  # only on create/connect when newly issued
    domain_id: Optional[UUID] = None
    published_at: Optional[datetime] = None
    update_available: bool = False
    latest_available_version: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TemplateListPage(BaseModel):
    items: List[TemplateResponse]
    total: int
    limit: int
    offset: int
    sort: str = "featured"


class CategoryItem(BaseModel):
    slug: str
    name: str
    count: int = 0
    icon: Optional[str] = None
    template_count: Optional[int] = None
    popularity_score: int = 0
    is_featured: bool = False
    description: Optional[str] = None


class MarketplaceDashboard(BaseModel):
    featured: List[TemplateResponse]
    newest: List[TemplateResponse]
    installed_count: int
    updates_count: int
    categories: List[CategoryItem]


class CollectionSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str = ""
    icon: Optional[str] = None
    banner_url: Optional[str] = None
    is_featured: bool = False
    sort_order: int = 100
    collection_type: str = "curated"
    item_count: int = 0


class CollectionDetail(CollectionSummary):
    items: List[TemplateResponse] = Field(default_factory=list)
    computed_rule: Dict[str, Any] = Field(default_factory=dict)


class CollectionCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(..., min_length=2, max_length=200)
    description: str = ""
    icon: Optional[str] = None
    banner_url: Optional[str] = None
    is_public: bool = True
    is_featured: bool = False
    sort_order: int = 100
    collection_type: str = "curated"
    computed_rule: Dict[str, Any] = Field(default_factory=dict)
    template_ids: List[UUID] = Field(default_factory=list)


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    banner_url: Optional[str] = None
    is_public: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None
    collection_type: Optional[str] = None
    computed_rule: Optional[Dict[str, Any]] = None
    template_ids: Optional[List[UUID]] = None


class MarketplaceHomeResponse(BaseModel):
    featured: List[TemplateResponse] = Field(default_factory=list)
    newest: List[TemplateResponse] = Field(default_factory=list)
    trending: List[TemplateResponse] = Field(default_factory=list)
    top_rated: List[TemplateResponse] = Field(default_factory=list)
    most_installed: List[TemplateResponse] = Field(default_factory=list)
    editors_choice: List[TemplateResponse] = Field(default_factory=list)
    continue_using: List[TemplateResponse] = Field(default_factory=list)
    recently_installed: List[TemplateResponse] = Field(default_factory=list)
    recently_viewed: List[TemplateResponse] = Field(default_factory=list)
    categories: List[CategoryItem] = Field(default_factory=list)
    collections: List[CollectionSummary] = Field(default_factory=list)
    installed_count: int = 0
    updates_count: int = 0


class UpdateNotification(BaseModel):
    installation_id: UUID
    template_id: UUID
    template_slug: str
    template_name: str
    installed_version: str
    latest_version: str
    changelog: Optional[str] = None


class AnalyticsCountItem(BaseModel):
    key: str
    label: str
    count: int


class AnalyticsDayPoint(BaseModel):
    day: str
    installs: int


class AnalyticsTemplateRank(BaseModel):
    template_id: UUID
    slug: str
    name: str
    kind: str = "package"
    category: str
    install_count: int = 0
    status: Optional[str] = None


class CompanyMarketplaceAnalytics(BaseModel):
    installed_count: int = 0
    updates_available: int = 0
    favorites_count: int = 0
    by_status: List[AnalyticsCountItem] = Field(default_factory=list)
    by_category: List[AnalyticsCountItem] = Field(default_factory=list)
    by_kind: List[AnalyticsCountItem] = Field(default_factory=list)
    installs_over_time: List[AnalyticsDayPoint] = Field(default_factory=list)
    recent_installs: List[AnalyticsTemplateRank] = Field(default_factory=list)


class CatalogMarketplaceAnalytics(BaseModel):
    templates_total: int = 0
    published: int = 0
    draft: int = 0
    archived: int = 0
    favorites_total: int = 0
    active_installs: int = 0
    by_kind: List[AnalyticsCountItem] = Field(default_factory=list)
    by_category: List[AnalyticsCountItem] = Field(default_factory=list)
    by_pricing_tier: List[AnalyticsCountItem] = Field(default_factory=list)
    top_templates: List[AnalyticsTemplateRank] = Field(default_factory=list)
    installs_over_time: List[AnalyticsDayPoint] = Field(default_factory=list)


class MarketplaceAnalytics(BaseModel):
    company: CompanyMarketplaceAnalytics
    catalog: Optional[CatalogMarketplaceAnalytics] = None
    days: int = 30
