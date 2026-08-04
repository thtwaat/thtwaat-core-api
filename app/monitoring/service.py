"""
Monitoring & Admin Operations service.

Aggregates platform state and ops controls by reusing:
  - app.deploy.health / metrics / DeployDashboardService
  - Enterprise audit + Usage / Billing / Marketplace / Product Generator
  - NotificationService for alert delivery
  - Redis thtwaat:jobs worker queue (scripts/worker.py)

Does NOT re-implement Prometheus scrape exposition (Instrumentator /metrics).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase
from app.agent_platform.models.agent import AgentConfig
from app.companies.model import Company
from app.config.settings import settings
from app.deploy import health as health_mod
from app.deploy import metrics as metrics_mod
from app.deploy.service import DeployDashboardService
from app.enterprise.models import AuditSeverity, EnterpriseAuditLog
from app.enterprise.service import EnterpriseService
from app.marketplace.models import InstallStatus, TemplateInstallation
from app.monitoring import queue as queue_mod
from app.monitoring.models import (
    AlertSeverity,
    AlertStatus,
    DeploymentAction,
    OpsAdminActivity,
    OpsAlert,
    OpsDeploymentEvent,
)
from app.monitoring.schemas import (
    AlertAckRequest,
    AlertCreateRequest,
    AlertListResponse,
    AlertResolveRequest,
    AlertResponse,
    AuditExportResponse,
    AuditTimelineResponse,
    AdminActivityResponse,
    CancelJobRequest,
    DeploymentEventResponse,
    EnqueueJobRequest,
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
from app.notifications.model import NotificationChannel
from app.notifications.schema import SendNotificationRequest
from app.notifications.service import NotificationService
from app.onboarding.models import OnboardingSession
from app.onboarding.steps import OnboardingStatus
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.subscriptions.model import Subscription, SubscriptionStatus
from app.product_generator.models import ProductGeneration
from app.users.model import User, UserStatus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


class MonitoringOpsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.notifications = NotificationService(db)
        self.enterprise = EnterpriseService(db)
        self.deploy = DeployDashboardService(db)

    # ── Admin dashboard ───────────────────────────────────────────────────────

    def platform_overview(self) -> PlatformOverviewResponse:
        active_users = (
            self.db.scalar(
                select(func.count(User.id)).where(
                    User.is_active.is_(True),
                    User.status == UserStatus.ACTIVE,
                )
            )
            or 0
        )
        companies = (
            self.db.scalar(
                select(func.count(Company.id)).where(Company.is_active.is_(True))
            )
            or 0
        )
        agents = self.db.scalar(select(func.count(AgentConfig.id))) or 0
        published_agents = (
            self.db.scalar(
                select(func.count(AgentConfig.id)).where(AgentConfig.status == "PUBLISHED")
            )
            or 0
        )
        knowledge_bases = self.db.scalar(select(func.count(KnowledgeBase.id))) or 0
        marketplace_installs = (
            self.db.scalar(
                select(func.count(TemplateInstallation.id)).where(
                    TemplateInstallation.status != InstallStatus.UNINSTALLED
                )
            )
            or 0
        )
        product_generations = self.db.scalar(select(func.count(ProductGeneration.id))) or 0

        paid = (
            self.db.scalar(
                select(func.coalesce(func.sum(Invoice.amount_paid), 0)).where(
                    Invoice.status == InvoiceStatus.PAID
                )
            )
            or 0
        )
        open_due = (
            self.db.scalar(
                select(func.coalesce(func.sum(Invoice.amount_due), 0)).where(
                    Invoice.status == InvoiceStatus.OPEN
                )
            )
            or 0
        )
        active_subs = (
            self.db.scalar(
                select(func.count(Subscription.id)).where(
                    Subscription.status.in_(
                        [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
                    )
                )
            )
            or 0
        )

        onboarding_total = self.db.scalar(select(func.count(OnboardingSession.id))) or 0
        onboarding_completed = (
            self.db.scalar(
                select(func.count(OnboardingSession.id)).where(
                    OnboardingSession.status == OnboardingStatus.COMPLETED
                )
            )
            or 0
        )

        deployments = {
            "published_agents": published_agents,
            "queue": queue_mod.queue_stats(),
            "certificates": metrics_mod.certificates_expiring(self.db),
        }

        return PlatformOverviewResponse(
            active_users=int(active_users),
            companies=int(companies),
            agents=int(agents),
            published_agents=int(published_agents),
            knowledge_bases=int(knowledge_bases),
            deployments=deployments,
            marketplace_installs=int(marketplace_installs),
            product_generations=int(product_generations),
            billing_summary={
                "active_subscriptions": int(active_subs),
                "revenue_paid": float(paid),
                "amount_due_open": float(open_due),
            },
            onboarding={
                "sessions": int(onboarding_total),
                "completed": int(onboarding_completed),
                "completion_rate": round(
                    (onboarding_completed / onboarding_total) * 100.0, 2
                )
                if onboarding_total
                else 0.0,
            },
            generated_at=_now(),
        )

    def impersonate_company(
        self,
        actor_id: UUID,
        body: ImpersonateCompanyRequest,
        ip: Optional[str] = None,
    ) -> ImpersonateCompanyResponse:
        """Issue JWT for the company owner (or first admin) — reuses AuthService tokens."""
        from app.auth.service import AuthService, ACCESS_TOKEN_EXPIRE_MINUTES
        from app.companies.model import CompanyStatus
        from app.rbac.enums import EnterpriseRole
        from app.users.model import User, UserStatus

        company = self.db.get(Company, body.company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        if not company.is_active or company.status == CompanyStatus.CANCELLED:
            raise HTTPException(status_code=403, detail="Company is inactive or cancelled")

        preferred = [
            EnterpriseRole.COMPANY_OWNER,
            EnterpriseRole.ADMIN,
            EnterpriseRole.MANAGER,
        ]
        target = None
        for role in preferred:
            target = self.db.scalar(
                select(User).where(
                    User.company_id == company.id,
                    User.role == role,
                    User.is_active.is_(True),
                    User.status == UserStatus.ACTIVE,
                )
            )
            if target:
                break
        if not target:
            raise HTTPException(
                status_code=404,
                detail="No active owner/admin user found for this company",
            )

        auth = AuthService(self.db)
        access = auth.create_access_token(subject=str(target.id))
        refresh = auth.create_refresh_token(subject=str(target.id))
        self._record_activity(
            actor_id,
            "impersonation",
            "login_as_company",
            "company",
            str(company.id),
            ip,
            {
                "target_user_id": str(target.id),
                "target_email": target.email,
                "reason": body.reason,
            },
        )
        self.db.commit()
        return ImpersonateCompanyResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            company_id=company.id,
            company_name=company.name,
            company_slug=company.slug,
            user_id=target.id,
            user_email=target.email,
            user_role=target.role.value if hasattr(target.role, "value") else str(target.role),
            impersonated_by=actor_id,
        )

    # ── System health ─────────────────────────────────────────────────────────

    async def system_health(self) -> SystemHealthResponse:
        full = await health_mod.full_health(self.db)
        checks = full.get("checks") or {}
        qstats = queue_mod.queue_stats()
        api = {
            "ok": full.get("status") in ("healthy", "degraded"),
            "status": full.get("status"),
            "uptime_seconds": metrics_mod.snapshot().get("uptime_seconds"),
        }
        email_queue = {"ok": True, "status": "not_configured", "depth": 0}
        try:
            # Best-effort: reuse Redis job queue stats as background/email worker signal
            email_queue = {
                "ok": True,
                "status": "ok" if int(qstats.get("queued") or 0) < 1000 else "backlog",
                "depth": int(qstats.get("queued") or 0),
                "note": "Uses ops job queue depth; dedicated email queue not separately instrumented.",
            }
        except Exception:
            pass
        return SystemHealthResponse(
            status=full.get("status") or "unknown",
            api=api,
            database=checks.get("database") or {},
            redis=checks.get("redis") or {},
            queue=qstats,
            storage=checks.get("storage") or {},
            workers=checks.get("workers") or {},
            ai_providers=checks.get("ai_providers") or {},
            email_queue=email_queue,
            background_jobs=qstats,
        )

    def observability(self) -> ObservabilityResponse:
        snap = metrics_mod.snapshot(self.db)
        cache = queue_mod.cache_hit_ratio()
        requests = int(snap.get("api_requests") or 0)
        errors = int(snap.get("errors") or 0)
        error_rate = round(errors / requests, 4) if requests else 0.0
        db_latency = health_mod.check_database(self.db)

        grafana = settings.GRAFANA_URL
        prometheus = settings.PROMETHEUS_URL

        dashboards = [
            {"name": "Prometheus Targets", "url": f"{prometheus}/targets"},
            {"name": "Grafana Home", "url": grafana},
            {"name": "API Metrics (Prom)", "url": f"{prometheus}/graph"},
        ]

        return ObservabilityResponse(
            prometheus_url=prometheus,
            grafana_url=grafana,
            grafana_dashboards=dashboards,
            latency={
                "database_ms": db_latency.get("latency_ms"),
                "note": "HTTP latency histograms live in Prometheus via Instrumentator /metrics",
            },
            error_rates={
                "in_process_error_rate": error_rate,
                "errors": errors,
                "requests": requests,
                "note": "Prefer Prometheus http_request metrics for production SLOs",
            },
            request_volume={
                "api_requests": requests,
                "messages_total": snap.get("messages_total"),
                "messages_per_min": snap.get("messages_per_min"),
            },
            queue_depth=int(snap.get("queue_depth") or 0),
            cache_hit_ratio=cache.get("hit_ratio"),
            snapshot=snap,
        )

    # ── Operations: jobs ──────────────────────────────────────────────────────

    def list_jobs(self, limit: int = 50) -> JobListResponse:
        return JobListResponse(
            active=queue_mod.list_jobs(limit=limit, dead=False),
            dead_letter=queue_mod.list_jobs(limit=limit, dead=True),
            stats=queue_mod.queue_stats(),
        )

    def retry_job(
        self, actor_id: UUID, body: RetryJobRequest, ip: Optional[str] = None
    ) -> Dict[str, Any]:
        result = queue_mod.retry_dead(index=body.index)
        self._record_deployment(
            DeploymentAction.JOB_RETRY,
            actor_id,
            status="success",
            target=f"dead[{body.index}]",
            message="Retried dead-letter job",
            details=result,
        )
        self._record_activity(
            actor_id, "operations", "job.retry", "job", str(body.index), ip, result
        )
        self.db.commit()
        return result

    def cancel_job(
        self, actor_id: UUID, body: CancelJobRequest, ip: Optional[str] = None
    ) -> Dict[str, Any]:
        result = queue_mod.cancel_job(index=body.index, dead=body.dead, job_id=body.job_id)
        self._record_deployment(
            DeploymentAction.JOB_CANCEL,
            actor_id,
            status="success",
            target=f"{'dead' if body.dead else 'active'}[{body.index}]",
            message="Cancelled queued job",
            details=result,
        )
        self._record_activity(
            actor_id, "operations", "job.cancel", "job", str(body.index), ip, result
        )
        self.db.commit()
        return result

    def enqueue_job(
        self, actor_id: UUID, body: EnqueueJobRequest, ip: Optional[str] = None
    ) -> Dict[str, Any]:
        payload = {"type": body.type, **body.payload}
        result = queue_mod.enqueue(payload)
        self._record_deployment(
            DeploymentAction.JOB_ENQUEUE,
            actor_id,
            status="success",
            target=body.type,
            message="Enqueued job",
            details=result,
        )
        self._record_activity(
            actor_id, "operations", "job.enqueue", "job", body.type, ip, result
        )
        self.db.commit()
        return result

    def deployment_history(self, limit: int = 50) -> List[DeploymentEventResponse]:
        rows = (
            self.db.query(OpsDeploymentEvent)
            .order_by(OpsDeploymentEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [DeploymentEventResponse.model_validate(r) for r in rows]

    def publish_queue(self, limit: int = 20) -> PublishQueueResponse:
        draft = (
            self.db.scalar(
                select(func.count(AgentConfig.id)).where(AgentConfig.status == "DRAFT")
            )
            or 0
        )
        published = (
            self.db.scalar(
                select(func.count(AgentConfig.id)).where(AgentConfig.status == "PUBLISHED")
            )
            or 0
        )
        recent = (
            self.db.query(AgentConfig)
            .filter(AgentConfig.status == "PUBLISHED", AgentConfig.published_at.isnot(None))
            .order_by(AgentConfig.published_at.desc())
            .limit(limit)
            .all()
        )
        return PublishQueueResponse(
            draft_agents=int(draft),
            published_agents=int(published),
            recent_publishes=[
                {
                    "agent_id": str(a.id),
                    "company_id": str(a.company_id),
                    "name": a.name,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                }
                for a in recent
            ],
        )

    # ── Alerts ────────────────────────────────────────────────────────────────

    def evaluate_and_raise(self, actor_company_id: Optional[UUID] = None) -> List[AlertResponse]:
        """Raise alerts from health/queue signals (idempotent via fingerprint)."""
        raised: List[AlertResponse] = []
        q = queue_mod.queue_stats()
        workers = health_mod.check_workers()

        rules = []
        if not workers.get("ok"):
            rules.append(
                (
                    AlertSeverity.CRITICAL,
                    "Background worker heartbeat missing",
                    "Worker heartbeat key thtwaat:worker:heartbeat is absent.",
                    "workers",
                    "worker_heartbeat",
                    workers,
                )
            )
        depth = int(q.get("queue_depth") or 0)
        if depth >= 100:
            rules.append(
                (
                    AlertSeverity.CRITICAL,
                    "Job queue depth critical",
                    f"Active queue depth is {depth}.",
                    "queue",
                    "queue_depth",
                    q,
                )
            )
        elif depth >= 25:
            rules.append(
                (
                    AlertSeverity.WARNING,
                    "Job queue depth elevated",
                    f"Active queue depth is {depth}.",
                    "queue",
                    "queue_depth",
                    q,
                )
            )
        dead = int(q.get("dead_letter_depth") or 0)
        if dead >= 1:
            rules.append(
                (
                    AlertSeverity.WARNING,
                    "Dead-letter jobs present",
                    f"{dead} job(s) in thtwaat:jobs:dead.",
                    "queue",
                    "dead_letter",
                    q,
                )
            )

        db_c = health_mod.check_database(self.db)
        if not db_c.get("ok"):
            rules.append(
                (
                    AlertSeverity.CRITICAL,
                    "Database health check failed",
                    str(db_c.get("error") or "database unavailable"),
                    "database",
                    "db_health",
                    db_c,
                )
            )

        for severity, title, body, source, metric, details in rules:
            alert = self._upsert_alert(
                severity=severity,
                title=title,
                body=body,
                source=source,
                metric=metric,
                details=details,
                company_id=actor_company_id,
                notify_push=True,
                notify_email=False,
            )
            if alert:
                raised.append(alert)
        self.db.commit()
        return raised

    def create_alert(
        self, actor_id: UUID, body: AlertCreateRequest, ip: Optional[str] = None
    ) -> AlertResponse:
        alert = self._upsert_alert(
            severity=body.severity,
            title=body.title,
            body=body.body,
            source=body.source,
            metric=body.metric,
            details=body.details,
            company_id=body.company_id,
            notify_push=body.notify_push,
            notify_email=body.notify_email,
            email_recipient=body.email_recipient,
            actor_id=actor_id,
            force_new=True,
        )
        self._record_activity(
            actor_id,
            "monitoring",
            "alert.create",
            "ops_alert",
            str(alert.id),
            ip,
            {"severity": body.severity.value},
        )
        self.db.commit()
        self.db.refresh(alert)
        return AlertResponse.model_validate(alert)

    def list_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        limit: int = 50,
    ) -> AlertListResponse:
        q = self.db.query(OpsAlert)
        if status:
            q = q.filter(OpsAlert.status == status)
        if severity:
            q = q.filter(OpsAlert.severity == severity)
        total = q.count()
        rows = q.order_by(OpsAlert.created_at.desc()).limit(limit).all()
        critical_open = (
            self.db.scalar(
                select(func.count(OpsAlert.id)).where(
                    OpsAlert.status == AlertStatus.OPEN,
                    OpsAlert.severity == AlertSeverity.CRITICAL,
                )
            )
            or 0
        )
        warning_open = (
            self.db.scalar(
                select(func.count(OpsAlert.id)).where(
                    OpsAlert.status == AlertStatus.OPEN,
                    OpsAlert.severity == AlertSeverity.WARNING,
                )
            )
            or 0
        )
        resolved = (
            self.db.scalar(
                select(func.count(OpsAlert.id)).where(OpsAlert.status == AlertStatus.RESOLVED)
            )
            or 0
        )
        return AlertListResponse(
            total=total,
            items=[AlertResponse.model_validate(r) for r in rows],
            critical_open=int(critical_open),
            warning_open=int(warning_open),
            resolved=int(resolved),
        )

    def acknowledge_alert(
        self,
        alert_id: UUID,
        actor_id: UUID,
        body: AlertAckRequest,
        ip: Optional[str] = None,
    ) -> AlertResponse:
        alert = self.db.get(OpsAlert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        if alert.status == AlertStatus.RESOLVED:
            raise HTTPException(status_code=400, detail="Alert already resolved")
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = actor_id
        alert.acknowledged_at = _now()
        details = dict(alert.details or {})
        if body.note:
            details["ack_note"] = body.note
        alert.details = details
        self._record_activity(
            actor_id, "monitoring", "alert.ack", "ops_alert", str(alert_id), ip, details
        )
        self.db.commit()
        self.db.refresh(alert)
        return AlertResponse.model_validate(alert)

    def resolve_alert(
        self,
        alert_id: UUID,
        actor_id: UUID,
        body: AlertResolveRequest,
        ip: Optional[str] = None,
    ) -> AlertResponse:
        alert = self.db.get(OpsAlert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.status = AlertStatus.RESOLVED
        alert.resolved_by = actor_id
        alert.resolved_at = _now()
        details = dict(alert.details or {})
        if body.note:
            details["resolve_note"] = body.note
        alert.details = details
        self._record_activity(
            actor_id,
            "monitoring",
            "alert.resolve",
            "ops_alert",
            str(alert_id),
            ip,
            details,
        )
        self.db.commit()
        self.db.refresh(alert)
        return AlertResponse.model_validate(alert)

    # ── Audit ─────────────────────────────────────────────────────────────────

    def audit_timeline(self, limit: int = 50) -> AuditTimelineResponse:
        activities = (
            self.db.query(OpsAdminActivity)
            .order_by(OpsAdminActivity.created_at.desc())
            .limit(limit)
            .all()
        )
        ops = (
            self.db.query(OpsDeploymentEvent)
            .order_by(OpsDeploymentEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        security = (
            self.db.query(EnterpriseAuditLog)
            .filter(
                EnterpriseAuditLog.severity.in_(
                    [AuditSeverity.WARNING, AuditSeverity.CRITICAL]
                )
            )
            .order_by(EnterpriseAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        sample = (
            self.db.query(EnterpriseAuditLog)
            .order_by(EnterpriseAuditLog.created_at.desc())
            .limit(min(limit, 25))
            .all()
        )
        return AuditTimelineResponse(
            admin_activities=[AdminActivityResponse.model_validate(a) for a in activities],
            operational_events=[DeploymentEventResponse.model_validate(o) for o in ops],
            security_events=[
                {
                    "id": str(s.id),
                    "company_id": str(s.company_id),
                    "action": s.action,
                    "severity": s.severity.value if hasattr(s.severity, "value") else s.severity,
                    "resource_type": s.resource_type,
                    "resource_id": s.resource_id,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in security
            ],
            enterprise_audit_sample=[
                {
                    "id": str(s.id),
                    "action": s.action,
                    "severity": s.severity.value if hasattr(s.severity, "value") else s.severity,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sample
            ],
        )

    def export_audit(self, fmt: str = "csv") -> AuditExportResponse:
        timeline = self.audit_timeline(limit=500)
        rows: List[Dict[str, Any]] = []
        for a in timeline.admin_activities:
            rows.append(
                {
                    "kind": "admin_activity",
                    "id": str(a.id),
                    "action": a.action,
                    "category": a.category,
                    "actor": str(a.actor_user_id) if a.actor_user_id else "",
                    "created_at": a.created_at.isoformat(),
                }
            )
        for o in timeline.operational_events:
            rows.append(
                {
                    "kind": "operational",
                    "id": str(o.id),
                    "action": o.action.value,
                    "category": "operations",
                    "actor": str(o.actor_user_id) if o.actor_user_id else "",
                    "created_at": o.created_at.isoformat(),
                }
            )
        for s in timeline.security_events:
            rows.append(
                {
                    "kind": "security",
                    "id": s["id"],
                    "action": s["action"],
                    "category": "security",
                    "actor": "",
                    "created_at": s.get("created_at") or "",
                }
            )

        if fmt == "json":
            content = json.dumps(rows, indent=2)
        else:
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf, fieldnames=["kind", "id", "action", "category", "actor", "created_at"]
            )
            writer.writeheader()
            writer.writerows(rows)
            content = buf.getvalue()

        return AuditExportResponse(
            format=fmt if fmt in ("csv", "json") else "csv",
            generated_at=_now(),
            row_count=len(rows),
            content=content,
        )

    # ── Reports ───────────────────────────────────────────────────────────────

    def platform_report(self, period: str = "daily") -> PlatformReportResponse:
        period = (period or "daily").lower()
        if period not in ("daily", "weekly", "monthly"):
            raise HTTPException(status_code=422, detail="period must be daily|weekly|monthly")
        end = _now()
        if period == "daily":
            start = end - timedelta(days=1)
        elif period == "weekly":
            start = end - timedelta(days=7)
        else:
            start = end - timedelta(days=30)

        new_companies = (
            self.db.scalar(
                select(func.count(Company.id)).where(Company.created_at >= start)
            )
            or 0
        )
        new_users = (
            self.db.scalar(select(func.count(User.id)).where(User.created_at >= start))
            or 0
        )
        new_agents = (
            self.db.scalar(
                select(func.count(AgentConfig.id)).where(AgentConfig.created_at >= start)
            )
            or 0
        )
        new_gens = (
            self.db.scalar(
                select(func.count(ProductGeneration.id)).where(
                    ProductGeneration.created_at >= start
                )
            )
            or 0
        )
        new_installs = (
            self.db.scalar(
                select(func.count(TemplateInstallation.id)).where(
                    TemplateInstallation.created_at >= start
                )
            )
            or 0
        )

        revenue = (
            self.db.scalar(
                select(func.coalesce(func.sum(Invoice.amount_paid), 0)).where(
                    Invoice.status == InvoiceStatus.PAID,
                    Invoice.created_at >= start,
                )
            )
            or 0
        )
        invoices_paid = (
            self.db.scalar(
                select(func.count(Invoice.id)).where(
                    Invoice.status == InvoiceStatus.PAID,
                    Invoice.created_at >= start,
                )
            )
            or 0
        )

        # Usage trends from daily aggregates when available
        usage_trends: Dict[str, Any] = {"period_start": start.isoformat(), "note": None}
        try:
            from app.usage.models import UsageDailyAggregate

            usage_rows = (
                self.db.query(UsageDailyAggregate)
                .filter(UsageDailyAggregate.day >= start)
                .limit(500)
                .all()
            )
            usage_trends["daily_aggregate_rows"] = len(usage_rows)
            usage_trends["sample"] = [
                {
                    "company_id": str(r.company_id),
                    "day": str(r.day),
                    "dimension": getattr(r, "dimension", None),
                    "quantity": float(getattr(r, "quantity", 0) or 0),
                }
                for r in usage_rows[:20]
            ]
        except Exception as exc:
            usage_trends["note"] = f"usage aggregates unavailable: {exc}"
            usage_trends["proxy"] = {
                "new_agents": int(new_agents),
                "new_product_generations": int(new_gens),
                "new_marketplace_installs": int(new_installs),
            }

        return PlatformReportResponse(
            period=period,
            range_start=start,
            range_end=end,
            platform_growth={
                "new_companies": int(new_companies),
                "new_users": int(new_users),
                "new_agents": int(new_agents),
                "new_product_generations": int(new_gens),
                "new_marketplace_installs": int(new_installs),
                "companies_total": int(
                    self.db.scalar(select(func.count(Company.id))) or 0
                ),
                "users_total": int(self.db.scalar(select(func.count(User.id))) or 0),
            },
            revenue_summary={
                "paid_amount": float(revenue),
                "paid_invoices": int(invoices_paid),
                "active_subscriptions": int(
                    self.db.scalar(
                        select(func.count(Subscription.id)).where(
                            Subscription.status.in_(
                                [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
                            )
                        )
                    )
                    or 0
                ),
            },
            usage_trends=usage_trends,
            generated_at=_now(),
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _fingerprint(self, source: str, metric: Optional[str], title: str) -> str:
        raw = f"{source}|{metric or ''}|{title}".encode()
        return hashlib.sha256(raw).hexdigest()[:32]

    def _upsert_alert(
        self,
        *,
        severity: AlertSeverity,
        title: str,
        body: str,
        source: str,
        metric: Optional[str],
        details: Dict[str, Any],
        company_id: Optional[UUID],
        notify_push: bool,
        notify_email: bool,
        email_recipient: Optional[str] = None,
        actor_id: Optional[UUID] = None,
        force_new: bool = False,
    ) -> Optional[OpsAlert]:
        fp = self._fingerprint(source, metric, title)
        if not force_new:
            existing = (
                self.db.query(OpsAlert)
                .filter(
                    OpsAlert.fingerprint == fp,
                    OpsAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
                )
                .first()
            )
            if existing:
                existing.details = _jsonable(details) if isinstance(details, dict) else details
                existing.severity = severity
                existing.body = body
                self.db.add(existing)
                return existing

        channels: List[str] = []
        alert = OpsAlert(
            severity=severity,
            status=AlertStatus.OPEN,
            title=title,
            body=body,
            source=source,
            metric=metric,
            fingerprint=fp if not force_new else self._fingerprint(source, metric, f"{title}:{_now().isoformat()}"),
            details=_jsonable(details) if isinstance(details, dict) else {"value": details},
            company_id=company_id,
            notified_channels=channels,
        )
        self.db.add(alert)
        self.db.flush()

        # Notify via existing NotificationService (in-app / push / email providers)
        notify_company = company_id
        if notify_company is None:
            # Platform alerts attach to first active company for inbox routing if needed
            first = self.db.scalar(select(Company.id).where(Company.is_active.is_(True)).limit(1))
            notify_company = first

        if notify_company and notify_push:
            try:
                from app.notifications.events import NotificationEventBus

                NotificationEventBus.dispatch(
                    event_type="ops.alert",
                    db=self.db,
                    company_id=notify_company,
                    user_id=actor_id,
                    data={
                        "title": title,
                        "severity": severity.value,
                        "alert_id": str(alert.id),
                    },
                )
                channels.append("in_app")
            except Exception as exc:
                logger.warning("alert in-app notify failed: %s", exc)
            if actor_id:
                try:
                    self.notifications.send_notification(
                        SendNotificationRequest(
                            channel=NotificationChannel.PUSH,
                            recipient=str(actor_id),
                            subject=f"[{severity.value.upper()}] {title}",
                            body=body,
                            template_name="ops_alert",
                            template_data={"severity": severity.value, "title": title},
                        ),
                        company_id=notify_company,
                        user_id=actor_id,
                    )
                    channels.append("push")
                except Exception as exc:
                    logger.warning("alert push notify failed: %s", exc)

        if notify_company and notify_email and email_recipient and actor_id:
            try:
                self.notifications.send_notification(
                    SendNotificationRequest(
                        channel=NotificationChannel.EMAIL,
                        recipient=email_recipient,
                        subject=f"[{severity.value.upper()}] {title}",
                        body=body,
                    ),
                    company_id=notify_company,
                    user_id=actor_id,
                )
                channels.append("email")
            except Exception as exc:
                logger.warning("alert email notify failed: %s", exc)

        alert.notified_channels = channels
        self.db.add(alert)
        return alert

    def _record_deployment(
        self,
        action: DeploymentAction,
        actor_id: Optional[UUID],
        *,
        status: str,
        target: Optional[str],
        message: Optional[str],
        details: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
    ) -> OpsDeploymentEvent:
        row = OpsDeploymentEvent(
            action=action,
            status=status,
            actor_user_id=actor_id,
            company_id=company_id,
            target=target,
            message=message,
            details=_jsonable(details or {}),
        )
        self.db.add(row)
        return row

    def _record_activity(
        self,
        actor_id: Optional[UUID],
        category: str,
        action: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        ip: Optional[str],
        details: Optional[Dict[str, Any]] = None,
    ) -> OpsAdminActivity:
        row = OpsAdminActivity(
            actor_user_id=actor_id,
            category=category,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip,
            details=_jsonable(details or {}),
        )
        self.db.add(row)
        return row
