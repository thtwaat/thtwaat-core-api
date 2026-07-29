"""Usage / cost tracker for the AI gateway."""
from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class Tracker:
    """
    Handles logging token usage and calculating costs.
    """

    @staticmethod
    def calculate_cost(input_tokens: int, output_tokens: int, model_config: dict) -> float:
        """Calculates cost based on model pricing."""
        prompt_cost = (input_tokens / 1000) * model_config.get("cost_per_1k_prompt", 0)
        completion_cost = (output_tokens / 1000) * model_config.get("cost_per_1k_completion", 0)
        return prompt_cost + completion_cost

    @staticmethod
    def log_usage(
        company_id: str,
        agent_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_cost: float,
        *,
        api_key_id: str | None = None,
        widget_id: str | None = None,
        source: str = "gateway",
        is_widget: bool = False,
        create_conversation: bool = False,
        db=None,
    ):
        """Writes usage into the Usage Meter (and legacy CompanyQuota tokens)."""
        if db is None:
            logger.debug(
                "usage_skip company_id=%s agent_id=%s tokens=%s (no db session)",
                company_id,
                agent_id,
                input_tokens + output_tokens,
            )
            return
        try:
            from app.usage.service import UsageService

            UsageService(db).record_ai_usage(
                UUID(str(company_id)),
                prompt_tokens=int(input_tokens or 0),
                completion_tokens=int(output_tokens or 0),
                agent_id=UUID(str(agent_id)) if agent_id else None,
                api_key_id=UUID(str(api_key_id)) if api_key_id else None,
                widget_id=widget_id,
                source=source,
                is_widget=is_widget,
                create_conversation=create_conversation,
            )

            # Also bump legacy spend if quota row exists
            from app.agent_platform.models.quota import CompanyQuota

            quota = (
                db.query(CompanyQuota)
                .filter(CompanyQuota.company_id == UUID(str(company_id)))
                .first()
            )
            if quota and total_cost:
                quota.current_spend = float(quota.current_spend or 0) + float(total_cost)
                db.commit()
        except Exception as exc:
            # Re-raise HTTP 429 quota errors; swallow other metering failures
            from fastapi import HTTPException

            if isinstance(exc, HTTPException):
                raise
            logger.warning("Tracker.log_usage failed: %s", exc)
