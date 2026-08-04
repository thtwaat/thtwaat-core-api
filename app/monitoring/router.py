"""Admin, Operations, and Monitoring API routes (PLATFORM_ADMIN)."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.monitoring.enterprise_ops import EnterpriseOpsService
from app.monitoring.models import AlertSeverity, AlertStatus
from app.monitoring.schemas import (
    AdminExportRequest,
    AdminInviteUserRequest,
    AlertAckRequest,
    AlertCreateRequest,
    AlertListResponse,
    AlertResolveRequest,
    AlertResponse,
    AuditExportResponse,
    AuditTimelineResponse,
    CancelJobRequest,
    DeploymentEventResponse,
    EnqueueJobRequest,
    ExecutiveDashboardResponse,
    ImpersonateCompanyRequest,
    ImpersonateCompanyResponse,
    JobListResponse,
    ObservabilityResponse,
    PlatformOverviewResponse,
    PlatformReportResponse,
    PublishQueueResponse,
    RetryJobRequest,
    SystemHealthResponse,
)
from app.monitoring.service import MonitoringOpsService
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

admin_router = APIRouter(prefix="/admin", tags=["Platform Admin"])
operations_router = APIRouter(prefix="/operations", tags=["Admin Operations"])
monitoring_router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


def get_ops_service(db: Session = Depends(get_db)) -> MonitoringOpsService:
    return MonitoringOpsService(db)


def get_enterprise_ops(db: Session = Depends(get_db)) -> EnterpriseOpsService:
    return EnterpriseOpsService(db)


def require_platform_admin(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.PLATFORM_ADMIN)(user.role)
    return user


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ── /admin ────────────────────────────────────────────────────────────────────

@admin_router.get(
    "/overview",
    response_model=PlatformOverviewResponse,
    summary="Platform overview (users, companies, agents, billing, …)",
)
def admin_overview(
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.platform_overview()


@admin_router.get(
    "/executive",
    response_model=ExecutiveDashboardResponse,
    summary="Executive KPI dashboard (MRR/ARR/churn/AI usage/…)",
)
def admin_executive(
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
):
    return service.executive_dashboard()


@admin_router.get(
    "/ai-analytics",
    summary="AI analytics (requests, providers, latency, top prompts/agents)",
)
def admin_ai_analytics(
    days: int = Query(30, ge=1, le=90),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
) -> Dict[str, Any]:
    return service.ai_analytics(days=days)


@admin_router.get(
    "/workspaces/{company_id}/ops",
    summary="Workspace quotas, billing, AI and API usage for admin ops",
)
def admin_workspace_ops(
    company_id: UUID,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
) -> Dict[str, Any]:
    return service.workspace_ops(company_id)


@admin_router.get(
    "/logs",
    summary="Unified admin logs (audit/payment/webhook/auth/ai)",
)
def admin_unified_logs(
    category: str = Query("all", pattern="^(all|audit|payment|payments|webhook|webhooks|auth|authentication|ai)$"),
    limit: int = Query(50, ge=1, le=200),
    company_id: Optional[UUID] = Query(default=None),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
) -> Dict[str, Any]:
    return service.unified_logs(category=category, limit=limit, company_id=company_id)


@admin_router.get(
    "/marketplace-analytics",
    summary="Platform marketplace + publisher store analytics",
)
def admin_marketplace_analytics(
    days: int = Query(30, ge=1, le=90),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
) -> Dict[str, Any]:
    return service.marketplace_ops_analytics(days=days)


@admin_router.post(
    "/users/invite",
    summary="Invite / create a user in a workspace (platform admin)",
)
def admin_invite_user(
    payload: AdminInviteUserRequest,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
) -> Dict[str, Any]:
    return service.invite_user(
        actor_id=user.id,
        email=payload.email,
        company_id=payload.company_id,
        role=payload.role,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )


@admin_router.post(
    "/users/{user_id}/reset-password",
    summary="Issue a temporary password for a user (platform admin)",
)
def admin_reset_user_password(
    user_id: UUID,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
) -> Dict[str, Any]:
    return service.admin_reset_password(actor_id=user.id, user_id=user_id)


@admin_router.post(
    "/export",
    summary="Export executive / AI / logs / workspaces as CSV, Excel, or PDF",
)
def admin_export(
    payload: AdminExportRequest,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: EnterpriseOpsService = Depends(get_enterprise_ops),
) -> Dict[str, Any]:
    return service.export_dataset(payload.kind, payload.format)


@admin_router.get(
    "/reports/{period}",
    response_model=PlatformReportResponse,
    summary="Daily / weekly / monthly platform growth & revenue report",
)
def admin_report(
    period: str,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.platform_report(period)


@admin_router.post(
    "/impersonate/company",
    response_model=ImpersonateCompanyResponse,
    summary="Login as company (issue tokens for owner/admin)",
)
def impersonate_company(
    payload: ImpersonateCompanyRequest,
    request: Request,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.impersonate_company(user.id, payload, _client_ip(request))


@admin_router.get(
    "/audit/timeline",
    response_model=AuditTimelineResponse,
    summary="Admin activity + operational + security event timeline",
)
def admin_audit_timeline(
    limit: int = Query(50, ge=1, le=200),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.audit_timeline(limit)


@admin_router.get(
    "/audit/export",
    response_model=AuditExportResponse,
    summary="Export audit timeline (csv|json)",
)
def admin_audit_export(
    format: str = Query("csv", pattern="^(csv|json)$"),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.export_audit(format)


# ── /operations ───────────────────────────────────────────────────────────────

@operations_router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="List running/queued and dead-letter jobs",
)
def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.list_jobs(limit)


@operations_router.post(
    "/jobs/retry",
    summary="Retry a failed (dead-letter) job",
)
def retry_job(
    payload: RetryJobRequest,
    request: Request,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.retry_job(user.id, payload, _client_ip(request))


@operations_router.post(
    "/jobs/cancel",
    summary="Cancel a queued job",
)
def cancel_job(
    payload: CancelJobRequest,
    request: Request,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.cancel_job(user.id, payload, _client_ip(request))


@operations_router.post(
    "/jobs/enqueue",
    summary="Enqueue an ops job onto thtwaat:jobs",
)
def enqueue_job(
    payload: EnqueueJobRequest,
    request: Request,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.enqueue_job(user.id, payload, _client_ip(request))


@operations_router.get(
    "/deployments",
    response_model=list[DeploymentEventResponse],
    summary="Deployment / ops action history",
)
def deployment_history(
    limit: int = Query(50, ge=1, le=200),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.deployment_history(limit)


@operations_router.get(
    "/publish-queue",
    response_model=PublishQueueResponse,
    summary="Publish surface (draft vs published agents)",
)
def publish_queue(
    limit: int = Query(20, ge=1, le=100),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.publish_queue(limit)


# ── /monitoring ───────────────────────────────────────────────────────────────

@monitoring_router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="System health (API, DB, Redis, queue, storage, workers)",
)
async def monitoring_health(
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return await service.system_health()


@monitoring_router.get(
    "/observability",
    response_model=ObservabilityResponse,
    summary="Prometheus/Grafana links + derived latency/error/volume signals",
)
def monitoring_observability(
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.observability()


@monitoring_router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List ops alerts (critical / warning / resolved)",
)
def list_alerts(
    status: Optional[AlertStatus] = Query(default=None),
    severity: Optional[AlertSeverity] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.list_alerts(status, severity, limit)


@monitoring_router.post(
    "/alerts",
    response_model=AlertResponse,
    summary="Create an alert and optionally notify push/email",
)
def create_alert(
    payload: AlertCreateRequest,
    request: Request,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.create_alert(user.id, payload, _client_ip(request))


@monitoring_router.post(
    "/alerts/evaluate",
    response_model=list[AlertResponse],
    summary="Evaluate health/queue rules and raise alerts",
)
def evaluate_alerts(
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.evaluate_and_raise(actor_company_id=user.company_id)


@monitoring_router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge an alert",
)
def acknowledge_alert(
    alert_id: UUID,
    payload: AlertAckRequest,
    request: Request,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.acknowledge_alert(alert_id, user.id, payload, _client_ip(request))


@monitoring_router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolve an alert",
)
def resolve_alert(
    alert_id: UUID,
    payload: AlertResolveRequest,
    request: Request,
    user: UserProfileResponse = Depends(require_platform_admin),
    service: MonitoringOpsService = Depends(get_ops_service),
):
    return service.resolve_alert(alert_id, user.id, payload, _client_ip(request))
