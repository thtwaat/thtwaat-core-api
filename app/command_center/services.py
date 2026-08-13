"""Command Center — read-only platform metrics from existing Core tables."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent_platform.models.conversation import Conversation
from app.apps.model import App, AppStatus
from app.command_center.schemas import DashboardResponse
from app.companies.model import Company, CompanyPlan
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.plans.model import Plan
from app.payments.subscriptions.model import Subscription, SubscriptionStatus
from app.usage.models import CompanyUsageMeter


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
