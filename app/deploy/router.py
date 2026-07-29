"""Admin Deployment Dashboard API — /api/v1/deploy."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.deploy.service import DeployDashboardService
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

router = APIRouter(prefix="/deploy", tags=["Deployment Dashboard"])


def get_deploy_service(db: Session = Depends(get_db)) -> DeployDashboardService:
    return DeployDashboardService(db)


def require_admin(user: UserProfileResponse = Depends(get_current_user)):
    # Prefer platform admin; fall back to company admin domain manage
    role = (user.role or "").lower()
    if role in ("super_admin", "admin", "company_owner"):
        return user
    try:
        RequirePermission(Permission.DOMAINS_MANAGE)(user.role)
        return user
    except Exception:
        RequirePermission(Permission.PLATFORM_ADMIN)(user.role)
        return user


@router.get(
    "/dashboard",
    summary="Admin deployment dashboard (domains, SSL, nginx, health, containers)",
)
async def deploy_dashboard(
    user: UserProfileResponse = Depends(require_admin),
    service: DeployDashboardService = Depends(get_deploy_service),
    scope: str = Query(default="company", pattern="^(company|all)$"),
):
    company_id = None if scope == "all" and user.role == "super_admin" else UUID(str(user.company_id))
    return await service.overview(company_id)


@router.post("/backup", summary="Trigger full backup now")
def trigger_backup(
    user: UserProfileResponse = Depends(require_admin),
    service: DeployDashboardService = Depends(get_deploy_service),
):
    return service.trigger_backup()


@router.get("/backups", summary="List available backups")
def list_backups(
    user: UserProfileResponse = Depends(require_admin),
):
    from app.deploy import backup as backup_mod

    return {"backups": backup_mod.list_backups()}


@router.post("/nginx/reload", summary="Reload nginx")
def nginx_reload(
    user: UserProfileResponse = Depends(require_admin),
    service: DeployDashboardService = Depends(get_deploy_service),
):
    return service.reload_nginx()


@router.post("/containers/{service_name}/restart", summary="Restart a compose service")
def restart_container(
    service_name: str,
    user: UserProfileResponse = Depends(require_admin),
    service: DeployDashboardService = Depends(get_deploy_service),
):
    return service.restart_service(service_name)


@router.get("/logs/{service_name}", summary="Tail container logs")
def container_logs(
    service_name: str,
    lines: int = Query(default=100, ge=10, le=2000),
    user: UserProfileResponse = Depends(require_admin),
    service: DeployDashboardService = Depends(get_deploy_service),
):
    return service.recent_logs(service_name, lines)


@router.get("/metrics", summary="Ops metrics snapshot")
def ops_metrics(
    user: UserProfileResponse = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.deploy import metrics as metrics_mod

    return metrics_mod.snapshot(db)


@router.post("/ssl/renew-due", summary="Auto-renew certificates due within 30 days")
def renew_due(
    user: UserProfileResponse = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.ssl.manager import SslManager

    return {"results": SslManager(db).auto_renew_due()}
