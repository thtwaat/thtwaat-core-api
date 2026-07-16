from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
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
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id, AgentConfig.company_id == company_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Aggregate Total Cost
    total_cost = db.query(func.sum(UsageLog.total_cost)).filter(UsageLog.agent_id == agent_id).scalar() or 0.0
    
    # Aggregate Total Tokens
    total_prompt_tokens = db.query(func.sum(UsageLog.prompt_tokens)).filter(UsageLog.agent_id == agent_id).scalar() or 0
    total_completion_tokens = db.query(func.sum(UsageLog.completion_tokens)).filter(UsageLog.agent_id == agent_id).scalar() or 0
    
    # Usage by Provider
    provider_usage = db.query(
        UsageLog.provider_id, 
        func.count(UsageLog.id).label("calls"),
        func.sum(UsageLog.total_cost).label("cost")
    ).filter(UsageLog.agent_id == agent_id).group_by(UsageLog.provider_id).all()
    
    provider_stats = [{"provider": r.provider_id, "calls": r.calls, "cost": r.cost} for r in provider_usage]
    
    return {
        "total_cost": total_cost,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "provider_usage": provider_stats
    }
