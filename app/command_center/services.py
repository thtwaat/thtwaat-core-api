"""Command Center — read-only platform metrics + read-only AI CEO analysis."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent_platform.models.conversation import Conversation
from app.ai.providers.factory import AIProviderFactory
from app.apps.model import App, AppStatus
from app.command_center.schemas import CeoAnalysisResponse, DashboardResponse
from app.companies.model import Company, CompanyPlan
from app.config.settings import settings
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.plans.model import Plan
from app.payments.subscriptions.model import Subscription, SubscriptionStatus
from app.usage.models import CompanyUsageMeter

logger = logging.getLogger(__name__)

# Default models per provider (env AI_PROVIDER). No AgentConfig / workspace writes.
_PROVIDER_DEFAULT_MODELS: Dict[str, str] = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "anthropic": "claude-3-5-haiku-latest",
    "claude": "claude-3-5-haiku-latest",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
}

_CEO_SYSTEM = """You are a read-only AI CEO advisor for the THTWAAT platform founder.
Analyze ONLY the provided dashboard metrics.
Rules (mandatory):
- Advisory only. Never claim you executed, sent, paid, deployed, or changed anything.
- No tools. No emails. No messages. No payments. No GitHub. No database writes. No automation.
- The human founder remains in full control.
Return ONLY a single JSON object with these keys:
{
  "business_status": "string — concise business status summary",
  "problems": ["string", "..."],
  "opportunities": ["string", "..."],
  "you_must_decide": ["string", "string", "string"],
  "recommendations": ["string", "..."]
}
you_must_decide MUST contain exactly 3 items.
Be specific and grounded in the numbers. Do not invent metrics not present in the input.
"""


class CommandCenterService:
    """Aggregates existing Core API data. No writes. No fake metrics."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_metrics(self) -> DashboardResponse:
        billing = self._billing_kpis()
        customers = self._active_customers()
        return DashboardResponse(
            revenue=billing["revenue"],
            mrr=billing["mrr"],
            customers=customers,
            active_projects=self._active_projects(),
            leads=self._leads_count(),
            conversion=self._conversion_rate(customers),
            ai_tasks=self._ai_tasks(),
            human_escalations=self._human_escalations(),
            ai_cost=self._ai_cost(),
        )

    async def analyze_ceo(self) -> CeoAnalysisResponse:
        """
        Read-only AI CEO analysis from live dashboard metrics.
        Uses AIProviderFactory directly — no AIService, agents, tools, or persistence.
        """
        metrics = self.get_dashboard_metrics()
        provider_name = (settings.AI_PROVIDER or "openai").strip().lower()
        model = _PROVIDER_DEFAULT_MODELS.get(provider_name, "gpt-4o-mini")

        metrics_json = metrics.model_dump_json()
        prompt = (
            f"{_CEO_SYSTEM}\n\n"
            f"Dashboard metrics JSON:\n{metrics_json}\n\n"
            "Return the JSON object now."
        )

        provider = AIProviderFactory.get_provider(provider_name)
        result = await provider.generate(
            prompt=prompt,
            model=model,
            temperature=0.2,
            max_tokens=1200,
        )

        parsed = self._parse_ceo_json(result.content or "")
        you_must_decide = self._normalize_three(parsed.get("you_must_decide"))

        return CeoAnalysisResponse(
            generated_at=datetime.now(timezone.utc),
            metrics_snapshot=metrics,
            business_status=str(parsed.get("business_status") or "Unable to summarize status.").strip(),
            problems=self._as_str_list(parsed.get("problems")),
            opportunities=self._as_str_list(parsed.get("opportunities")),
            you_must_decide=you_must_decide,
            recommendations=self._as_str_list(parsed.get("recommendations")),
            provider=provider_name,
            model_used=(result.model_used or model) or model,
        )

    @staticmethod
    def _parse_ceo_json(text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                logger.warning("CEO analysis JSON extract failed")
        return {}

    @staticmethod
    def _as_str_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        out: List[str] = []
        for item in value:
            s = str(item).strip()
            if s:
                out.append(s)
        return out

    @classmethod
    def _normalize_three(cls, value: Any) -> List[str]:
        items = cls._as_str_list(value)
        while len(items) < 3:
            items.append("Review the metrics and decide the next founder priority.")
        return items[:3]

    def _billing_kpis(self) -> Dict[str, float]:
        """Same definitions as /payments/admin/analytics (read-only)."""
        active_statuses = [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,
        ]
        subs = (
            self.db.query(Subscription)
            .filter(Subscription.status.in_(active_statuses))
            .all()
        )
        plan_cache: Dict[Any, Plan] = {}
        mrr = Decimal("0")
        for sub in subs:
            plan = plan_cache.get(sub.plan_id)
            if plan is None:
                plan = self.db.get(Plan, sub.plan_id)
                plan_cache[sub.plan_id] = plan
            if not plan:
                continue
            amount = Decimal(str(plan.amount or 0))
            if (plan.interval or "month").lower() == "year":
                amount = amount / Decimal("12")
            mrr += amount

        paid = (
            self.db.query(func.coalesce(func.sum(Invoice.amount_paid), 0))
            .filter(Invoice.status == InvoiceStatus.PAID)
            .scalar()
        )
        return {
            "mrr": float(mrr),
            "revenue": float(paid or 0),
        }

    def _active_customers(self) -> int:
        return int(
            self.db.query(func.count(Company.id))
            .filter(Company.is_active.is_(True))
            .scalar()
            or 0
        )

    def _active_projects(self) -> int:
        """Active tenant apps (existing product surfaces)."""
        return int(
            self.db.query(func.count(App.id))
            .filter(App.status == AppStatus.ACTIVE)
            .scalar()
            or 0
        )

    def _leads_count(self) -> int:
        """Conversations that captured a lead in metadata (agent platform)."""
        try:
            return int(
                self.db.query(func.count(Conversation.id))
                .filter(Conversation.extra_metadata.has_key("lead"))
                .scalar()
                or 0
            )
        except Exception:
            # Dialect without JSONB has_key — fall back to scanning metadata.
            rows = self.db.query(Conversation.extra_metadata).all()
            return sum(
                1
                for (meta,) in rows
                if isinstance(meta, dict) and isinstance(meta.get("lead"), dict)
            )

    def _conversion_rate(self, total_active: int) -> float:
        """% of active companies on a paid plan (same idea as enterprise ops)."""
        if total_active <= 0:
            return 0.0
        paid = int(
            self.db.query(func.count(Company.id))
            .filter(
                Company.is_active.is_(True),
                Company.plan != CompanyPlan.FREE,
            )
            .scalar()
            or 0
        )
        return round((paid / total_active) * 100.0, 2)

    def _ai_tasks(self) -> int:
        """Platform AI message volume from usage meters (monthly periods)."""
        return int(
            self.db.query(func.coalesce(func.sum(CompanyUsageMeter.ai_messages), 0))
            .filter(CompanyUsageMeter.period_type == "monthly")
            .scalar()
            or 0
        )

    def _human_escalations(self) -> int:
        return int(
            self.db.query(func.count(Conversation.id))
            .filter(Conversation.status.in_(("pending_human", "human")))
            .scalar()
            or 0
        )

    def _ai_cost(self) -> float:
        return float(
            self.db.query(func.coalesce(func.sum(CompanyUsageMeter.estimated_cost), 0))
            .filter(CompanyUsageMeter.period_type == "monthly")
            .scalar()
            or 0
        )
