"""Pydantic schemas for Monitoring & Admin Operations."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.monitoring.models import AlertSeverity, AlertStatus, DeploymentAction


# ── Admin overview ────────────────────────────────────────────────────────────

class PlatformOverviewResponse(BaseModel):
    active_users: int
    companies: int
    agents: int
    published_agents: int
    knowledge_bases: int
    deployments: Dict[str, Any] = Field(default_factory=dict)
    marketplace_installs: int
    product_generations: int
    billing_summary: Dict[str, Any] = Field(default_factory=dict)
    onboarding: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime


# ── System health / observability ─────────────────────────────────────────────

class SystemHealthResponse(BaseModel):
    status: str
    api: Dict[str, Any]
    database: Dict[str, Any]
    redis: Dict[str, Any]
    queue: Dict[str, Any]
    storage: Dict[str, Any]
    workers: Dict[str, Any]
    ai_providers: Dict[str, Any] = Field(default_factory=dict)


class ObservabilityResponse(BaseModel):
    """
    Links and derived signals — does NOT re-export Prometheus scrape text.
    Prefer Grafana /metrics for time-series; this endpoint is for admin UX.
    """
    prometheus_url: str
    grafana_url: str
    metrics_endpoint: str = "/metrics"
    deploy_metrics_endpoint: str = "/api/v1/deploy/metrics"
    grafana_dashboards: List[Dict[str, str]] = Field(default_factory=list)
    latency: Dict[str, Any] = Field(default_factory=dict)
    error_rates: Dict[str, Any] = Field(default_factory=dict)
    request_volume: Dict[str, Any] = Field(default_factory=dict)
    queue_depth: int = 0
    cache_hit_ratio: Optional[float] = None
    snapshot: Dict[str, Any] = Field(default_factory=dict)


# ── Operations ────────────────────────────────────────────────────────────────

class JobListResponse(BaseModel):
    active: List[Dict[str, Any]] = Field(default_factory=list)
    dead_letter: List[Dict[str, Any]] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)


class RetryJobRequest(BaseModel):
    index: int = Field(0, ge=0)
    dead: bool = True


class CancelJobRequest(BaseModel):
    index: int = Field(0, ge=0)
    dead: bool = False
    job_id: Optional[str] = None


class EnqueueJobRequest(BaseModel):
    type: str = Field(..., min_length=1, max_length=100)
    payload: Dict[str, Any] = Field(default_factory=dict)


class DeploymentEventResponse(BaseModel):
    id: UUID
    action: DeploymentAction
    status: str
    actor_user_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    target: Optional[str] = None
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublishQueueResponse(BaseModel):
    """Publish is synchronous today — surface draft/published agent counts as the 'queue'."""
    draft_agents: int
    published_agents: int
    recent_publishes: List[Dict[str, Any]] = Field(default_factory=list)
    note: str = "Agent publish is synchronous via PublishService; no async publish queue exists."


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertCreateRequest(BaseModel):
    severity: AlertSeverity = AlertSeverity.WARNING
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    source: str = Field(default="manual", max_length=100)
    metric: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    company_id: Optional[UUID] = None
    notify_push: bool = True
    notify_email: bool = False
    email_recipient: Optional[str] = None


class AlertAckRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=500)


class AlertResolveRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=500)


class AlertResponse(BaseModel):
    id: UUID
    severity: AlertSeverity
    status: AlertStatus
    title: str
    body: str
    source: str
    metric: Optional[str] = None
    fingerprint: str
    details: Dict[str, Any] = Field(default_factory=dict)
    notified_channels: List[str] = Field(default_factory=list)
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    company_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    total: int
    items: List[AlertResponse]
    critical_open: int
    warning_open: int
    resolved: int


# ── Audit / reports ───────────────────────────────────────────────────────────

class AdminActivityResponse(BaseModel):
    id: UUID
    actor_user_id: Optional[UUID] = None
    category: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditTimelineResponse(BaseModel):
    admin_activities: List[AdminActivityResponse]
    operational_events: List[DeploymentEventResponse]
    security_events: List[Dict[str, Any]] = Field(default_factory=list)
    enterprise_audit_sample: List[Dict[str, Any]] = Field(default_factory=list)


class AuditExportResponse(BaseModel):
    format: str
    generated_at: datetime
    row_count: int
    content: str


class PlatformReportResponse(BaseModel):
    period: str  # daily | weekly | monthly
    range_start: datetime
    range_end: datetime
    platform_growth: Dict[str, Any]
    revenue_summary: Dict[str, Any]
    usage_trends: Dict[str, Any]
    generated_at: datetime
