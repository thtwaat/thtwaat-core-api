from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID

from app.database.database import get_db
from app.auth.dependencies import get_current_user_and_company
from app.agent_platform.models.usage_log import UsageLog
from app.agent_platform.models.agent import AgentConfig

router = APIRouter(prefix="/v2/agents/{agent_id}/analytics", tags=["Agent Analytics"])


@router.get("")
def get_agent_analytics(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    company_id = auth_data.get("company_id")
    agent = (
        db.query(AgentConfig.id)
        .filter(AgentConfig.id == agent_id, AgentConfig.company_id == company_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Single aggregate query instead of three separate SUM scans
    totals = (
        db.query(
            func.coalesce(func.sum(UsageLog.total_cost), 0.0),
            func.coalesce(func.sum(UsageLog.prompt_tokens), 0),
            func.coalesce(func.sum(UsageLog.completion_tokens), 0),
        )
        .filter(UsageLog.agent_id == agent_id)
        .one()
    )
    total_cost, total_prompt_tokens, total_completion_tokens = totals

    provider_usage = (
        db.query(
            UsageLog.provider_id,
            func.count(UsageLog.id).label("calls"),
            func.sum(UsageLog.total_cost).label("cost"),
        )
        .filter(UsageLog.agent_id == agent_id)
        .group_by(UsageLog.provider_id)
        .all()
    )

    provider_stats = [
        {"provider": r.provider_id, "calls": r.calls, "cost": r.cost} for r in provider_usage
    ]

    return {
        "total_cost": float(total_cost or 0),
        "total_tokens": int(total_prompt_tokens or 0) + int(total_completion_tokens or 0),
        "prompt_tokens": int(total_prompt_tokens or 0),
        "completion_tokens": int(total_completion_tokens or 0),
        "provider_usage": provider_stats,
    }
