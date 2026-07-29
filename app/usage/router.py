"""Usage Meter FastAPI router."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.usage.service import UsageService
from app.usage.schemas import (
    CurrentUsageResponse,
    MonthlySummaryResponse,
    RecordUsageRequest,
    ResetUsageRequest,
    UsageDashboardResponse,
    UsageHistoryResponse,
    MeterResponse,
    UsageCounters,
    UsageLimits,
)
from app.usage.dimensions import UsageDimension

router = APIRouter(prefix="/usage", tags=["Usage Meter"])


def get_usage_service(db: Session = Depends(get_db)) -> UsageService:
    return UsageService(db)


@router.get(
    "/current",
    response_model=CurrentUsageResponse,
    summary="Current period usage + plan limits",
)
def get_current_usage(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    return service.current_usage(UUID(str(current_user.company_id)))


@router.get(
    "/history",
    response_model=UsageHistoryResponse,
    summary="Daily usage history",
)
def get_usage_history(
    days: int = Query(default=30, ge=1, le=365),
    dimension: Optional[str] = Query(default=None),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    return service.history(UUID(str(current_user.company_id)), days=days, dimension=dimension)


@router.get(
    "/monthly-summary",
    response_model=MonthlySummaryResponse,
    summary="Monthly usage summary",
)
def get_monthly_summary(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    return service.monthly_summary(UUID(str(current_user.company_id)))


@router.get(
    "/dashboard",
    response_model=UsageDashboardResponse,
    summary="Usage dashboard (cards, progress, tops, storage)",
)
def get_usage_dashboard(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    return service.dashboard(UUID(str(current_user.company_id)))


@router.get(
    "/top/agents",
    summary="Top agents by usage",
)
def top_agents(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    current = service.current_usage(UUID(str(current_user.company_id)))
    return service.repo.top_by_metadata(
        UUID(str(current_user.company_id)), "agent_id", since=current.period_start
    )


@router.get(
    "/top/api-keys",
    summary="Top API keys by usage",
)
def top_api_keys(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    current = service.current_usage(UUID(str(current_user.company_id)))
    return service.repo.top_by_metadata(
        UUID(str(current_user.company_id)), "api_key_id", since=current.period_start
    )


@router.get(
    "/top/widgets",
    summary="Top widgets by usage",
)
def top_widgets(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    current = service.current_usage(UUID(str(current_user.company_id)))
    return service.repo.top_by_metadata(
        UUID(str(current_user.company_id)), "widget_id", since=current.period_start
    )


@router.get(
    "/storage",
    summary="Storage breakdown",
)
def storage_breakdown(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    summary = service.monthly_summary(UUID(str(current_user.company_id)))
    return {
        "knowledge_upload_bytes": summary.usage.knowledge_upload_bytes,
        "storage_bytes": summary.usage.storage_bytes,
        "limit": summary.limits.max_storage,
    }


@router.post(
    "/record",
    response_model=MeterResponse,
    summary="[Internal/Admin] Record a usage event",
    status_code=status.HTTP_201_CREATED,
)
def record_usage(
    body: RecordUsageRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    dim = UsageDimension(body.dimension)
    meter = service.record(
        UUID(str(current_user.company_id)),
        dim,
        body.quantity,
        agent_id=body.agent_id,
        api_key_id=body.api_key_id,
        widget_id=body.widget_id,
        source=body.source or "manual",
        metadata=body.metadata,
        enforce=True,
    )
    return MeterResponse(
        id=meter.id,
        company_id=meter.company_id,
        plan_key=meter.plan_key,
        period_type=meter.period_type,
        period_start=meter.period_start,
        period_end=meter.period_end,
        usage=UsageCounters(
            ai_messages=meter.ai_messages,
            conversations=meter.conversations,
            prompt_tokens=meter.prompt_tokens,
            completion_tokens=meter.completion_tokens,
            total_tokens=meter.total_tokens,
            api_requests=meter.api_requests,
            widget_requests=meter.widget_requests,
            knowledge_searches=meter.knowledge_searches,
            knowledge_upload_bytes=meter.knowledge_upload_bytes,
            storage_bytes=meter.storage_bytes,
            agents_count=meter.agents_count,
            active_users=meter.active_users,
            api_keys=meter.api_keys,
            domains=meter.domains,
            templates_published=meter.templates_published,
        ),
        limits=UsageLimits(
            max_agents=meter.max_agents,
            max_messages=meter.max_messages,
            max_tokens=int(meter.max_tokens),
            max_storage=int(meter.max_storage),
            max_domains=meter.max_domains,
            max_team_members=meter.max_team_members,
            max_api_keys=meter.max_api_keys,
            max_templates=meter.max_templates,
        ),
    )


@router.post(
    "/reset",
    response_model=CurrentUsageResponse,
    summary="[Admin] Manual monthly usage reset",
)
def reset_usage(
    body: ResetUsageRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UsageService = Depends(get_usage_service),
):
    role = getattr(current_user, "role", None)
    role_val = role.value if hasattr(role, "value") else str(role or "")
    if role_val.lower() not in ("admin", "owner", "superadmin", "super_admin"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required to reset usage")
    service.reset_monthly(UUID(str(current_user.company_id)), reason=body.reason)
    return service.current_usage(UUID(str(current_user.company_id)))
