"""Blueprint schema, validation warnings, and API payloads."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.studio.models import StudioProjectStatus


# ── Project (Phase 1) ─────────────────────────────────────────────────────────

class StudioProjectCreate(BaseModel):
    prompt: str = Field(..., min_length=8, max_length=20_000)
    title: Optional[str] = Field(None, max_length=255)

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if len(cleaned) < 8:
            raise ValueError("Prompt must be at least 8 characters")
        return cleaned

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class StudioProjectResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: Optional[UUID] = None
    title: str
    prompt: str
    status: StudioProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudioProjectListResponse(BaseModel):
    items: list[StudioProjectResponse]
    total: int


# ── Blueprint (Phase 2) ───────────────────────────────────────────────────────

class ProductBlueprint(BaseModel):
    industry: str = "general"
    product_type: str = "saas"
    target_users: List[str] = Field(default_factory=list)
    pages: List[str] = Field(default_factory=list)
    dashboard_modules: List[str] = Field(default_factory=list)
    backend_modules: List[str] = Field(default_factory=list)
    database_tables: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    authentication: Dict[str, Any] = Field(default_factory=dict)
    billing: Dict[str, Any] = Field(default_factory=dict)
    payments: Dict[str, Any] = Field(default_factory=dict)
    ai_features: List[str] = Field(default_factory=list)
    knowledge: Dict[str, Any] = Field(default_factory=dict)
    workflows: List[str] = Field(default_factory=list)
    integrations: List[str] = Field(default_factory=list)
    deployment: Dict[str, Any] = Field(default_factory=dict)
    marketplace_category: str = "saas"
    estimated_complexity: str = "medium"
    estimated_build_time: str = "2-4 weeks"

    model_config = {"extra": "allow"}


class BlueprintWarning(BaseModel):
    code: str
    severity: str = "warn"  # info | warn | error
    message: str
    field: Optional[str] = None


class BlueprintRecommendations(BaseModel):
    templates: List[str] = Field(default_factory=list)
    marketplace_assets: List[str] = Field(default_factory=list)
    agents: List[str] = Field(default_factory=list)
    knowledge_packs: List[str] = Field(default_factory=list)
    integrations: List[str] = Field(default_factory=list)


class StudioBlueprintResponse(BaseModel):
    id: UUID
    project_id: UUID
    workspace_id: UUID
    version: int
    is_current: bool
    source: str
    blueprint: ProductBlueprint
    warnings: List[BlueprintWarning] = Field(default_factory=list)
    recommendations: BlueprintRecommendations = Field(default_factory=BlueprintRecommendations)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudioBlueprintUpdate(BaseModel):
    blueprint: ProductBlueprint


class StudioBlueprintVersionSummary(BaseModel):
    id: UUID
    version: int
    is_current: bool
    source: str
    created_at: datetime
    warning_count: int = 0

    model_config = {"from_attributes": True}


class StudioBlueprintVersionList(BaseModel):
    items: List[StudioBlueprintVersionSummary]
    current_version: Optional[int] = None


class StudioAnalyzeResponse(BaseModel):
    project: StudioProjectResponse
    blueprint: StudioBlueprintResponse
