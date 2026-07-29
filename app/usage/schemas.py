"""Pydantic schemas for Usage Meter APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsageCounters(BaseModel):
    ai_messages: int = 0
    conversations: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_requests: int = 0
    widget_requests: int = 0
    knowledge_searches: int = 0
    knowledge_upload_bytes: int = 0
    storage_bytes: int = 0
    agents_count: int = 0
    active_users: int = 0
    api_keys: int = 0
    domains: int = 0
    templates_published: int = 0


class UsageLimits(BaseModel):
    max_agents: int
    max_messages: int
    max_tokens: int
    max_storage: int
    max_domains: int
    max_team_members: int
    max_api_keys: int
    max_templates: int


class UsageProgressItem(BaseModel):
    dimension: str
    current: int
    limit: int
    percent: float


class CurrentUsageResponse(BaseModel):
    company_id: UUID
    plan: str
    period_type: str
    period_start: datetime
    period_end: datetime
    usage: UsageCounters
    limits: UsageLimits
    progress: List[UsageProgressItem]
    upgrade_url: str = "/billing"


class UsageHistoryPoint(BaseModel):
    day: datetime
    dimension: str
    quantity: int


class UsageHistoryResponse(BaseModel):
    company_id: UUID
    points: List[UsageHistoryPoint]


class MonthlySummaryResponse(BaseModel):
    company_id: UUID
    plan: str
    period_start: datetime
    period_end: datetime
    usage: UsageCounters
    limits: UsageLimits
    estimated_monthly_tokens: int
    recent_events: List[Dict[str, Any]]


class UsageDashboardResponse(BaseModel):
    current: CurrentUsageResponse
    summary: MonthlySummaryResponse
    top_agents: List[Dict[str, Any]]
    top_api_keys: List[Dict[str, Any]]
    top_widgets: List[Dict[str, Any]]
    storage_breakdown: Dict[str, int]


class QuotaExceededDetail(BaseModel):
    error: str = "quota_exceeded"
    dimension: str
    current_usage: int
    plan_limit: int
    upgrade_url: str = "/billing"
    plan: str


class RecordUsageRequest(BaseModel):
    dimension: str
    quantity: int = Field(default=1, ge=0)
    agent_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    widget_id: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResetUsageRequest(BaseModel):
    reason: Optional[str] = None


class MeterResponse(BaseModel):
    id: UUID
    company_id: UUID
    plan_key: str
    period_type: str
    period_start: datetime
    period_end: datetime
    usage: UsageCounters
    limits: UsageLimits

    model_config = ConfigDict(from_attributes=True)
