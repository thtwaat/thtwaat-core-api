"""Usage quota FastAPI dependencies."""
from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.agent_platform.dependencies import verify_api_key
from app.agent_platform.models.api_key import AgentApiKey
from app.usage.dimensions import UsageDimension
from app.usage.service import UsageService


def require_quota(dimension: UsageDimension, quantity: int = 1) -> Callable:
    """Factory: enforce a usage dimension before the route handler runs."""

    def _dep(
        api_key: AgentApiKey = Depends(verify_api_key),
        db: Session = Depends(get_db),
    ) -> AgentApiKey:
        UsageService(db).check_quota(api_key.company_id, dimension, quantity=quantity)
        return api_key

    return _dep


def enforce_usage_quota(
    api_key: AgentApiKey = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> AgentApiKey:
    """Default public-chat quota gate: messages + tokens headroom."""
    svc = UsageService(db)
    svc.check_quota(api_key.company_id, UsageDimension.AI_MESSAGES, quantity=1)
    # Soft check — ensure at least 1 token headroom remains
    svc.check_quota(api_key.company_id, UsageDimension.TOTAL_TOKENS, quantity=1)
    return api_key


def get_usage_service(db: Session = Depends(get_db)) -> UsageService:
    return UsageService(db)
