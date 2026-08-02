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


class TemplateVersionCreate(BaseModel):
    version: str = Field(..., min_length=1, max_length=32)
    changelog: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    set_latest: bool = True


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

    model_config = ConfigDict(from_attributes=True)


class TemplateVersionResponse(BaseModel):
    id: UUID
    template_id: UUID
    version: str
    changelog: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    is_latest: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


class MarketplaceDashboard(BaseModel):
    featured: List[TemplateResponse]
    newest: List[TemplateResponse]
    installed_count: int
    updates_count: int
    categories: List[CategoryItem]


class UpdateNotification(BaseModel):
    installation_id: UUID
    template_id: UUID
    template_slug: str
    template_name: str
    installed_version: str
    latest_version: str
    changelog: Optional[str] = None
