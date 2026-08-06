"""Blueprint schema, validation warnings, and API payloads."""
from __future__ import annotations

import enum
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


# ── Compose / Build Plan (Phase 3) ────────────────────────────────────────────

class ModuleKind(str, enum.Enum):
    EXISTING = "existing_module"
    MARKETPLACE = "marketplace_template"
    CUSTOM = "custom_module"


class ComposedModule(BaseModel):
    key: str
    label: str
    kind: ModuleKind
    platform_ref: Optional[str] = None
    marketplace_template: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    reason: str = ""
    custom_effort: str = "none"  # none | low | medium | high
    category: str = "foundation"


class DependencyEdge(BaseModel):
    key: str
    label: str
    depends_on: List[str] = Field(default_factory=list)


class BuildPlanStep(BaseModel):
    order: int
    key: str
    label: str
    phase: str
    kind: ModuleKind
    depends_on: List[str] = Field(default_factory=list)
    platform_ref: Optional[str] = None
    marketplace_template: Optional[str] = None
    note: Optional[str] = None


class BuildPlanSummary(BaseModel):
    reuse_percent: float = 0.0
    existing_count: int = 0
    marketplace_count: int = 0
    custom_count: int = 0
    module_count: int = 0
    estimated_custom_work: str = "none"
    warnings: List[BlueprintWarning] = Field(default_factory=list)


class StudioComposeResult(BaseModel):
    """In-memory compose output (also stored on StudioProjectBuildPlan)."""

    modules: List[ComposedModule] = Field(default_factory=list)
    dependency_graph: List[DependencyEdge] = Field(default_factory=list)
    dependency_tree: List[Dict[str, Any]] = Field(default_factory=list)
    build_plan: List[BuildPlanStep] = Field(default_factory=list)
    summary: BuildPlanSummary = Field(default_factory=BuildPlanSummary)


class StudioBuildPlanResponse(BaseModel):
    id: UUID
    project_id: UUID
    workspace_id: UUID
    blueprint_version: int
    version: int
    is_current: bool
    modules: List[ComposedModule] = Field(default_factory=list)
    dependency_graph: List[DependencyEdge] = Field(default_factory=list)
    dependency_tree: List[Dict[str, Any]] = Field(default_factory=list)
    build_plan: List[BuildPlanStep] = Field(default_factory=list)
    summary: BuildPlanSummary = Field(default_factory=BuildPlanSummary)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudioComposeResponse(BaseModel):
    project: StudioProjectResponse
    build_plan: StudioBuildPlanResponse
