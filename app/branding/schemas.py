"""Pydantic schemas for white-label branding API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _hex_color(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    s = v.strip()
    if not s.startswith("#"):
        s = f"#{s}"
    if len(s) not in (4, 7, 9):
        raise ValueError("Color must be #RGB, #RRGGBB, or #RRGGBBAA")
    return s.upper() if len(s) > 4 else s


class EmailTemplates(BaseModel):
    welcome: Optional[str] = None
    password_reset: Optional[str] = None
    invoice: Optional[str] = None
    notification: Optional[str] = None


class EmailBranding(BaseModel):
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    logo_url: Optional[str] = None
    templates: EmailTemplates = Field(default_factory=EmailTemplates)


class MobileBranding(BaseModel):
    app_name: Optional[str] = None
    android_package: Optional[str] = None
    ios_bundle_id: Optional[str] = None
    splash_url: Optional[str] = None
    launcher_icon_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None

    @field_validator("primary_color", "secondary_color", mode="before")
    @classmethod
    def _colors(cls, v: Optional[str]) -> Optional[str]:
        return _hex_color(v)


class WidgetBrandingDefaults(BaseModel):
    launcher_icon_url: Optional[str] = None
    chat_theme: Optional[str] = "light"
    bubble_color: Optional[str] = None
    header_logo_url: Optional[str] = None
    suggested_prompts: List[str] = Field(default_factory=list)
    primary_color: Optional[str] = None
    font_family: Optional[str] = None

    @field_validator("bubble_color", "primary_color", mode="before")
    @classmethod
    def _colors(cls, v: Optional[str]) -> Optional[str]:
        return _hex_color(v)


class DomainRoles(BaseModel):
    """Hostname roles — SSL/verification handled by Domain Manager."""

    app: Optional[str] = None
    api: Optional[str] = None
    chat: Optional[str] = None


class BrandingUpdate(BaseModel):
    company_name: Optional[str] = None
    copyright_text: Optional[str] = None
    footer_text: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    font_family: Optional[str] = None
    heading_font: Optional[str] = None
    dashboard_theme: Optional[str] = None
    login_background_url: Optional[str] = None
    logo_url: Optional[str] = None
    dark_logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    email: Optional[EmailBranding] = None
    mobile: Optional[MobileBranding] = None
    widget: Optional[WidgetBrandingDefaults] = None
    domain_roles: Optional[DomainRoles] = None

    @field_validator("primary_color", "secondary_color", "accent_color", mode="before")
    @classmethod
    def _colors(cls, v: Optional[str]) -> Optional[str]:
        return _hex_color(v)

    @field_validator("dashboard_theme")
    @classmethod
    def _theme(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"light", "dark", "system"}
        if v not in allowed:
            raise ValueError(f"dashboard_theme must be one of {allowed}")
        return v


class BrandingAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_type: str
    url: str
    mime_type: str
    size_bytes: int
    version: int
    width: Optional[int] = None
    height: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None


class BrandingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    company_name: Optional[str] = None
    copyright_text: Optional[str] = None
    footer_text: Optional[str] = None
    primary_color: str
    secondary_color: str
    accent_color: str
    font_family: str
    heading_font: Optional[str] = None
    dashboard_theme: str
    login_background_url: Optional[str] = None
    logo_url: Optional[str] = None
    dark_logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    email: Dict[str, Any] = Field(default_factory=dict)
    mobile: Dict[str, Any] = Field(default_factory=dict)
    widget: Dict[str, Any] = Field(default_factory=dict)
    domain_roles: Dict[str, Any] = Field(default_factory=dict)
    draft_version: int
    published_version: int
    is_published: bool
    published_at: Optional[datetime] = None
    assets: List[BrandingAssetResponse] = Field(default_factory=list)


class BrandingPreviewResponse(BaseModel):
    """Editor preview: draft branding + live domain/SSL status (no downtime apply)."""

    branding: BrandingResponse
    published: Optional[Dict[str, Any]] = None
    domains: List[Dict[str, Any]] = Field(default_factory=list)
    css_variables: Dict[str, str] = Field(default_factory=dict)
    widget_preview: Dict[str, Any] = Field(default_factory=dict)
    email_preview: Dict[str, Any] = Field(default_factory=dict)
    mobile_preview: Dict[str, Any] = Field(default_factory=dict)


class BrandingPublishResponse(BaseModel):
    branding: BrandingResponse
    published_version: int
    applied: Dict[str, Any] = Field(default_factory=dict)


class PublicBrandingResponse(BaseModel):
    """Public white-label payload for app / widget hosts."""

    company_id: UUID
    company_slug: Optional[str] = None
    version: int
    branding: Dict[str, Any]
    css_variables: Dict[str, str] = Field(default_factory=dict)
