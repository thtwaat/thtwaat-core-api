"""Usage + cost metering for OpenAI-compatible completions (Week 2 Day 5)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.openai_compat.dependencies import CompletionsPrincipal

logger = logging.getLogger(__name__)


def estimate_completion_cost(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    company_id: UUID,
) -> float:
    """Reuse gateway Resolvers pricing table for cost estimates."""
    try:
        from app.agent_platform.gateway.resolvers import Resolvers
        from app.agent_platform.gateway.tracker import Tracker

        model_config = Resolvers.get_model_config(str(company_id), provider, model)
        return float(
            Tracker.calculate_cost(
                input_tokens=int(prompt_tokens or 0),
                output_tokens=int(completion_tokens or 0),
                model_config=model_config,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cost estimate failed provider=%s model=%s err=%s", provider, model, exc)
        return 0.0


def record_completion_usage(
    db: Session,
    principal: CompletionsPrincipal,
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    completion_id: str,
    source: str = "openai_compat",
) -> Dict[str, Any]:
    """
    Flush token usage into Usage Meter (daily aggregates + monthly meter) and
    bump legacy CompanyQuota spend when cost > 0.
    """
    cost = estimate_completion_cost(
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        company_id=principal.company_id,
    )
    summary: Dict[str, Any] = {
        "estimated_cost": cost,
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(prompt_tokens or 0) + int(completion_tokens or 0),
        "recorded": False,
    }
    try:
        from app.usage.service import UsageService
        from app.agent_platform.models.quota import CompanyQuota

        UsageService(db).record_ai_usage(
            principal.company_id,
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
            agent_id=principal.agent_id,
            api_key_id=principal.api_key_id,
            source=source,
            is_widget=False,
            create_conversation=False,
        )

        if cost:
            quota = (
                db.query(CompanyQuota)
                .filter(CompanyQuota.company_id == principal.company_id)
                .first()
            )
            if quota:
                quota.current_spend = float(quota.current_spend or 0) + float(cost)
                db.commit()

        summary["recorded"] = True
        summary["completion_id"] = completion_id
        summary["provider"] = provider
        summary["model"] = model
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise
        logger.warning(
            "openai_compat usage record failed company=%s completion=%s err=%s",
            principal.company_id,
            completion_id,
            exc,
        )
    return summary


def usage_analytics_payload(db: Session, company_id: UUID) -> Dict[str, Any]:
    """Monthly + daily analytics for the authenticated tenant."""
    from app.usage.service import UsageService

    svc = UsageService(db)
    current = svc.current_usage(company_id)
    history = svc.history(company_id, days=30, dimension="total_tokens")
    daily = [
        {
            "day": p.day.isoformat() if hasattr(p.day, "isoformat") else str(p.day),
            "dimension": p.dimension,
            "quantity": p.quantity,
        }
        for p in (history.points or [])
    ]
    return {
        "object": "thtwaat.usage",
        "company_id": str(company_id),
        "plan": current.plan,
        "period": {
            "type": current.period_type,
            "start": current.period_start.isoformat(),
            "end": current.period_end.isoformat(),
        },
        "monthly": {
            "ai_messages": current.usage.ai_messages,
            "prompt_tokens": current.usage.prompt_tokens,
            "completion_tokens": current.usage.completion_tokens,
            "total_tokens": current.usage.total_tokens,
            "api_requests": current.usage.api_requests,
        },
        "limits": {
            "max_messages": current.limits.max_messages,
            "max_tokens": current.limits.max_tokens,
        },
        "progress": [
            {
                "dimension": i.dimension,
                "current": i.current,
                "limit": i.limit,
                "percent": i.percent,
            }
            for i in current.progress
        ],
        "daily_token_usage": daily,
        "billing": {"upgrade_url": current.upgrade_url},
    }
