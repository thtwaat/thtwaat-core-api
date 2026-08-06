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


# ── Frontend Generator (Phase 4) ──────────────────────────────────────────────

class FrontendReuseRef(BaseModel):
    kind: str = "existing_page"  # existing_page | layout | component | existing_form
    path: str
    route: Optional[str] = None
    module_key: Optional[str] = None
    component: Optional[str] = None


class FrontendFormField(BaseModel):
    name: str
    type: str = "string"  # string | email | password | number | date | datetime | select | textarea | uuid
    required: bool = False
    label: str = ""
    list_column: bool = False


class FrontendFormSpec(BaseModel):
    id: str
    page_id: str
    title: str
    reuse: bool = False
    fields: List[FrontendFormField] = Field(default_factory=list)
    submit_label: str = "Save"


class FrontendCrudSpec(BaseModel):
    entity: str
    table: str
    operations: List[str] = Field(default_factory=lambda: ["list", "create", "update", "delete"])
    fields: List[FrontendFormField] = Field(default_factory=list)
    table_columns: List[str] = Field(default_factory=list)
    form_id: Optional[str] = None


class FrontendNavItem(BaseModel):
    id: str
    label: str
    route: str
    icon: str = "LayoutDashboard"
    page_id: str
    reuse: bool = True


class FrontendRoute(BaseModel):
    path: str
    page_id: str
    layout: str = "app"
    auth: str = "session"  # public | session
    reuse: bool = True


class FrontendPageSpec(BaseModel):
    id: str
    title: str
    kind: str = "reuse"  # reuse | generated_spec
    route: str
    layout: str = "app"
    auth: str = "session"
    module_key: Optional[str] = None
    reuse: Optional[FrontendReuseRef] = None
    reason: str = ""
    responsive: bool = True
    cards: List[Dict[str, Any]] = Field(default_factory=list)
    crud: Optional[FrontendCrudSpec] = None
    layout_slots: List[str] = Field(default_factory=list)
    preview: Dict[str, Any] = Field(default_factory=dict)


class FrontendSummary(BaseModel):
    page_count: int = 0
    reuse_page_count: int = 0
    generated_page_count: int = 0
    nav_item_count: int = 0
    route_count: int = 0
    form_count: int = 0
    reuse_percent: float = 0.0
    estimated_custom_work: str = "none"
    warnings: List[BlueprintWarning] = Field(default_factory=list)


class FrontendManifest(BaseModel):
    """Production-ready frontend preview plan — no Next.js source emission."""

    schema_version: int = 1
    product_name: str = "Untitled product"
    industry: str = "general"
    product_type: str = "saas"
    theme: Dict[str, Any] = Field(default_factory=dict)
    layouts: List[Dict[str, Any]] = Field(default_factory=list)
    design_system: Dict[str, str] = Field(default_factory=dict)
    nav: List[FrontendNavItem] = Field(default_factory=list)
    routes: List[FrontendRoute] = Field(default_factory=list)
    pages: List[FrontendPageSpec] = Field(default_factory=list)
    forms: List[FrontendFormSpec] = Field(default_factory=list)
    dashboard_cards: List[Dict[str, Any]] = Field(default_factory=list)
    responsive: Dict[str, Any] = Field(default_factory=dict)
    summary: FrontendSummary = Field(default_factory=FrontendSummary)
    traceability: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[BlueprintWarning] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class StudioFrontendResponse(BaseModel):
    id: UUID
    project_id: UUID
    workspace_id: UUID
    blueprint_version: int
    build_plan_version: int
    version: int
    is_current: bool
    status: str = "draft"  # draft | approved
    manifest: FrontendManifest
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudioFrontendGenerateResponse(BaseModel):
    project: StudioProjectResponse
    frontend: StudioFrontendResponse


class StudioFrontendUpdate(BaseModel):
    """Allow editing the frontend manifest before approval."""

    manifest: FrontendManifest
    status: Optional[str] = None  # draft | approved


# ── Backend Generator (Phase 5) ───────────────────────────────────────────────

class BackendApiEndpoint(BaseModel):
    id: str
    method: str
    path: str
    resource: str
    operation: str
    summary: str = ""
    permissions: List[str] = Field(default_factory=list)
    validation: Dict[str, Any] = Field(default_factory=dict)
    filters: List[str] = Field(default_factory=list)
    pagination: bool = False
    search: bool = False
    upload: bool = False
    reuse: bool = True
    module_key: Optional[str] = None
    platform_ref: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class BackendApiManifest(BaseModel):
    endpoints: List[BackendApiEndpoint] = Field(default_factory=list)
    resource_count: int = 0
    reuse_endpoint_count: int = 0
    custom_endpoint_count: int = 0


class BackendColumn(BaseModel):
    name: str
    type: str = "varchar"
    primary_key: bool = False
    nullable: bool = True
    indexed: bool = False
    unique: bool = False
    default: Optional[str] = None


class BackendTable(BaseModel):
    name: str
    reuse: bool = False
    module_key: Optional[str] = None
    platform_ref: Optional[str] = None
    columns: List[BackendColumn] = Field(default_factory=list)
    indexes: List[List[str]] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    migration: str = ""


class BackendRelationship(BaseModel):
    from_table: str
    to_table: str
    type: str = "many_to_one"
    foreign_key: str = ""
    via: str = ""


class BackendDatabaseManifest(BaseModel):
    tables: List[BackendTable] = Field(default_factory=list)
    relationships: List[BackendRelationship] = Field(default_factory=list)
    enums: List[Dict[str, Any]] = Field(default_factory=list)
    migrations: List[str] = Field(default_factory=list)
    reuse_table_count: int = 0
    custom_table_count: int = 0


class BackendServiceItem(BaseModel):
    id: str
    name: str
    kind: str = "business"  # business | job | webhook | event | notification
    reuse: bool = True
    module_key: Optional[str] = None
    platform_ref: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    events: List[str] = Field(default_factory=list)


class BackendRbacManifest(BaseModel):
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    policies: List[Dict[str, Any]] = Field(default_factory=list)
    reuse: bool = True
    platform_ref: str = "app/auth"
    note: str = ""


class BackendStorageItem(BaseModel):
    id: str
    kind: str  # files | images | documents | knowledge
    path: str
    reuse: bool = True
    module_key: Optional[str] = None
    platform_ref: Optional[str] = None


class BackendQueueItem(BaseModel):
    id: str
    name: str
    kind: str  # emails | notifications | ai_jobs | imports | exports
    reuse: bool = True
    module_key: Optional[str] = None
    workers: List[str] = Field(default_factory=list)
    events: List[str] = Field(default_factory=list)


class BackendOpenApiPreview(BaseModel):
    openapi: str = "3.0.3"
    info: Dict[str, Any] = Field(default_factory=dict)
    paths: Dict[str, Any] = Field(default_factory=dict)
    components: Dict[str, Any] = Field(default_factory=dict)


class BackendSummary(BaseModel):
    endpoint_count: int = 0
    table_count: int = 0
    service_count: int = 0
    role_count: int = 0
    storage_item_count: int = 0
    queue_count: int = 0
    reuse_percent: float = 0.0
    estimated_custom_work: str = "none"
    warnings: List[BlueprintWarning] = Field(default_factory=list)


class BackendManifest(BaseModel):
    """Backend architecture preview — no source emission / no deploy."""

    schema_version: int = 1
    product_name: str = "Untitled product"
    industry: str = "general"
    product_type: str = "saas"
    api: BackendApiManifest = Field(default_factory=BackendApiManifest)
    database: BackendDatabaseManifest = Field(default_factory=BackendDatabaseManifest)
    services: List[BackendServiceItem] = Field(default_factory=list)
    rbac: BackendRbacManifest = Field(default_factory=BackendRbacManifest)
    storage: List[BackendStorageItem] = Field(default_factory=list)
    queues: List[BackendQueueItem] = Field(default_factory=list)
    openapi: BackendOpenApiPreview = Field(default_factory=BackendOpenApiPreview)
    summary: BackendSummary = Field(default_factory=BackendSummary)
    traceability: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[BlueprintWarning] = Field(default_factory=list)
    note: str = ""

    model_config = {"extra": "allow"}


class StudioBackendResponse(BaseModel):
    id: UUID
    project_id: UUID
    workspace_id: UUID
    blueprint_version: int
    build_plan_version: int
    frontend_version: int
    version: int
    is_current: bool
    status: str = "draft"
    manifest: BackendManifest
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudioBackendGenerateResponse(BaseModel):
    project: StudioProjectResponse
    backend: StudioBackendResponse


class StudioBackendUpdate(BaseModel):
    manifest: BackendManifest
    status: Optional[str] = None


# ── AI Generator (Phase 6) ────────────────────────────────────────────────────

class AiProviderRecommendation(BaseModel):
    provider: str
    rank: int = 1
    score: float = 0.0
    reason: str = ""
    capabilities: List[str] = Field(default_factory=list)
    default_model: str = ""
    recommended_primary: bool = False
    platform_ref: str = "app/ai"


class AiModelRecommendation(BaseModel):
    task: str
    provider: str
    model: str
    plan_only: bool = False
    reason: str = ""
    fallbacks: List[Dict[str, str]] = Field(default_factory=list)


class AiAgentSpec(BaseModel):
    id: str
    name: str
    kind: str = "assistant"  # assistant | rag | workflow
    reuse: bool = True
    platform_ref: str = "app/agent_platform"
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    memory: bool = True
    knowledge: bool = False
    streaming: bool = True
    tools: List[str] = Field(default_factory=list)
    safety: List[str] = Field(default_factory=list)
    moderation: bool = True
    lead_capture: bool = False
    human_handoff: bool = True
    multi_language: bool = False
    voice_plan: bool = False
    vision_plan: bool = False
    widget: bool = False


class AiPromptTemplate(BaseModel):
    id: str
    name: str
    category: str = "system"
    agent_id: Optional[str] = None
    template: str
    variables: List[str] = Field(default_factory=list)
    reuse: bool = True
    platform_ref: Optional[str] = None


class AiToolSpec(BaseModel):
    id: str
    name: str
    description: str = ""
    reuse: bool = True
    platform_ref: Optional[str] = None
    parameters: Dict[str, str] = Field(default_factory=dict)
    permissions: List[str] = Field(default_factory=list)
    http: Optional[Dict[str, str]] = None


class AiWorkflowSpec(BaseModel):
    id: str
    name: str
    steps: List[str] = Field(default_factory=list)
    agent_id: Optional[str] = None
    reuse: bool = True
    platform_refs: List[str] = Field(default_factory=list)


class AiCostEstimate(BaseModel):
    currency: str = "USD"
    provider: str = "openai"
    monthly_requests: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_monthly_usd: float = 0.0
    notes: List[str] = Field(default_factory=list)
    metering_ref: str = "app/usage"
    billing_ref: str = "app/payments"


class AiSummary(BaseModel):
    provider_count: int = 0
    agent_count: int = 0
    prompt_count: int = 0
    tool_count: int = 0
    workflow_count: int = 0
    model_count: int = 0
    reuse_percent: float = 0.0
    estimated_monthly_usd: float = 0.0
    warnings: List[BlueprintWarning] = Field(default_factory=list)


class AiManifest(BaseModel):
    """AI architecture preview — reuses AI Gateway runtime, no app source emission."""

    schema_version: int = 1
    product_name: str = "Untitled product"
    industry: str = "general"
    product_type: str = "saas"
    runtime: Dict[str, Any] = Field(default_factory=dict)
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    providers: List[AiProviderRecommendation] = Field(default_factory=list)
    models: List[AiModelRecommendation] = Field(default_factory=list)
    agents: List[AiAgentSpec] = Field(default_factory=list)
    prompts: List[AiPromptTemplate] = Field(default_factory=list)
    tools: List[AiToolSpec] = Field(default_factory=list)
    workflows: List[AiWorkflowSpec] = Field(default_factory=list)
    knowledge: Dict[str, Any] = Field(default_factory=dict)
    memory: Dict[str, Any] = Field(default_factory=dict)
    safety: Dict[str, Any] = Field(default_factory=dict)
    cost: AiCostEstimate = Field(default_factory=AiCostEstimate)
    summary: AiSummary = Field(default_factory=AiSummary)
    traceability: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[BlueprintWarning] = Field(default_factory=list)
    note: str = ""

    model_config = {"extra": "allow"}


class StudioAiResponse(BaseModel):
    id: UUID
    project_id: UUID
    workspace_id: UUID
    blueprint_version: int
    build_plan_version: int
    frontend_version: int
    backend_version: int
    version: int
    is_current: bool
    status: str = "draft"
    manifest: AiManifest
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudioAiGenerateResponse(BaseModel):
    project: StudioProjectResponse
    ai: StudioAiResponse


class StudioAiUpdate(BaseModel):
    manifest: AiManifest
    status: Optional[str] = None
