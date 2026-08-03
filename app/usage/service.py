"""Usage metering service — record, enforce, reset, billing sync."""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.usage.dimensions import (
    DIMENSION_TO_LIMIT,
    GAUGE_DIMENSIONS,
    UsageDimension,
    limits_for_plan,
    resolve_plan_key,
)
from app.usage.models import UsageEvent, CompanyUsageMeter
from app.usage.repository import UsageRepository
from app.usage.schemas import (
    CurrentUsageResponse,
    MonthlySummaryResponse,
    QuotaExceededDetail,
    UsageCounters,
    UsageDashboardResponse,
    UsageHistoryPoint,
    UsageHistoryResponse,
    UsageLimits,
    UsageProgressItem,
)
from app.companies.repository import CompanyRepository
from app.agent_platform.models.quota import CompanyQuota

logger = logging.getLogger(__name__)

UPGRADE_URL = "/billing"


def month_period(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    last_day = monthrange(now.year, now.month)[1]
    end = datetime(now.year, now.month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


def day_floor(dt: datetime) -> datetime:
    dt = dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


class UsageService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UsageRepository(db)
        self.companies = CompanyRepository(db)

    # ── Period / meter bootstrap ──────────────────────────────────────────────

    def _plan_key_for_company(self, company_id: UUID) -> str:
        company = self.companies.get_by_id(company_id)
        if not company:
            return "free"
        plan = company.plan.value if hasattr(company.plan, "value") else str(company.plan)
        return resolve_plan_key(plan)

    def get_or_create_meter(
        self,
        company_id: UUID,
        *,
        period_type: str = "monthly",
        plan_key: Optional[str] = None,
    ) -> CompanyUsageMeter:
        start, end = month_period()
        if period_type == "lifetime":
            start = datetime(1970, 1, 1, tzinfo=timezone.utc)
            end = datetime(9999, 12, 31, tzinfo=timezone.utc)
        elif period_type == "daily":
            now = datetime.now(timezone.utc)
            start = day_floor(now)
            end = start + timedelta(days=1) - timedelta(seconds=1)
        elif period_type == "hourly":
            now = datetime.now(timezone.utc)
            start = datetime(now.year, now.month, now.day, now.hour, tzinfo=timezone.utc)
            end = start + timedelta(hours=1) - timedelta(seconds=1)

        meter = self.repo.get_meter(company_id, start, period_type)
        if meter:
            # Raise floor limits when product defaults increase (e.g. free max_domains 0→1)
            # without clobbering higher custom/paid caps already on the meter.
            key = resolve_plan_key(plan_key or meter.plan_key or self._plan_key_for_company(company_id))
            defaults = limits_for_plan(key)
            dirty = False
            for field, floor in defaults.items():
                if not hasattr(meter, field):
                    continue
                current = int(getattr(meter, field, 0) or 0)
                if current < int(floor):
                    setattr(meter, field, int(floor))
                    dirty = True
            if dirty:
                meter.plan_key = key
                self.repo.save_meter(meter)
            return meter

        key = plan_key or self._plan_key_for_company(company_id)
        limits = limits_for_plan(key)
        meter = self.repo.create_meter(
            {
                "company_id": company_id,
                "period_type": period_type,
                "period_start": start,
                "period_end": end,
                "plan_key": key,
                **{k: limits[k] for k in (
                    "max_agents",
                    "max_messages",
                    "max_tokens",
                    "max_storage",
                    "max_domains",
                    "max_team_members",
                    "max_api_keys",
                    "max_templates",
                )},
            }
        )
        return meter

    def _limits_from_plan_row(self, plan) -> Optional[Dict[str, int]]:
        """Prefer explicit plan columns when present."""
        if plan is None:
            return None
        keys = (
            "max_agents",
            "max_messages",
            "max_tokens",
            "max_storage",
            "max_domains",
            "max_team_members",
            "max_api_keys",
            "max_templates",
        )
        if not all(hasattr(plan, k) for k in keys):
            return None
        out = {k: int(getattr(plan, k) or 0) for k in keys}
        # Treat unset zeros on paid plans as "use defaults" only when all zero
        if all(v == 0 for v in out.values()):
            return None
        return out

    def apply_plan_limits(
        self,
        company_id: UUID,
        plan_name: str,
        *,
        plan_row=None,
        emit_upgraded: bool = True,
    ) -> CompanyUsageMeter:
        """Called after Razorpay/Stripe upgrade — refresh limits immediately."""
        key = resolve_plan_key(plan_name)
        limits = self._limits_from_plan_row(plan_row) or limits_for_plan(key)
        meter = self.get_or_create_meter(company_id, plan_key=key)
        meter.plan_key = key
        for k, v in limits.items():
            if hasattr(meter, k):
                setattr(meter, k, v)
        self.repo.save_meter(meter)

        # Keep legacy agent quota table in sync for token/spend checks
        quota = (
            self.db.query(CompanyQuota)
            .filter(CompanyQuota.company_id == company_id)
            .first()
        )
        if not quota:
            quota = CompanyQuota(company_id=company_id)
            self.db.add(quota)
        quota.monthly_token_limit = int(limits["max_tokens"])
        # rough spend ceiling: leave existing or scale with tier
        if key == "free":
            quota.monthly_spend_limit = 5.0
        elif key == "starter":
            quota.monthly_spend_limit = 50.0
        elif key in ("pro", "growth"):
            quota.monthly_spend_limit = 250.0
        elif key == "business":
            quota.monthly_spend_limit = 1000.0
        else:
            quota.monthly_spend_limit = 10000.0
        self.db.commit()

        if emit_upgraded:
            self._emit_webhook(company_id, "subscription.upgraded", {
                "plan": key,
                "limits": limits,
            })
        return meter

    def downgrade_to_free(self, company_id: UUID) -> CompanyUsageMeter:
        meter = self.apply_plan_limits(company_id, "free", emit_upgraded=False)
        self._emit_webhook(company_id, "subscription.expired", {"plan": "free"})
        return meter

    # ── Record / enforce ──────────────────────────────────────────────────────

    def _counter_attr(self, dimension: UsageDimension) -> str:
        return dimension.value

    def _current_value(self, meter: CompanyUsageMeter, dimension: UsageDimension) -> int:
        return int(getattr(meter, self._counter_attr(dimension), 0) or 0)

    def _limit_value(self, meter: CompanyUsageMeter, dimension: UsageDimension) -> Optional[int]:
        limit_key = DIMENSION_TO_LIMIT.get(dimension)
        if not limit_key:
            return None
        return int(getattr(meter, limit_key, 0) or 0)

    def check_quota(
        self,
        company_id: UUID,
        dimension: UsageDimension,
        *,
        quantity: int = 1,
        raise_http: bool = True,
    ) -> bool:
        if dimension in GAUGE_DIMENSIONS:
            # gauges checked as absolute set
            meter = self.get_or_create_meter(company_id)
            limit = self._limit_value(meter, dimension)
            if limit is None:
                return True
            current = self._current_value(meter, dimension)
            # for gauges, quantity is the new absolute value being set
            projected = quantity
            if projected > limit:
                if raise_http:
                    self._raise_quota(company_id, dimension, current, limit, meter.plan_key)
                return False
            return True

        meter = self.get_or_create_meter(company_id)
        limit = self._limit_value(meter, dimension)
        if limit is None:
            return True
        current = self._current_value(meter, dimension)
        if current + quantity > limit:
            if raise_http:
                self._emit_webhook(company_id, "quota.exceeded", {
                    "dimension": dimension.value,
                    "current_usage": current,
                    "plan_limit": limit,
                    "plan": meter.plan_key,
                })
                self._raise_quota(company_id, dimension, current, limit, meter.plan_key)
            return False
        return True

    def _raise_quota(
        self,
        company_id: UUID,
        dimension: UsageDimension,
        current: int,
        limit: int,
        plan: str,
    ) -> None:
        detail = QuotaExceededDetail(
            dimension=dimension.value,
            current_usage=current,
            plan_limit=limit,
            upgrade_url=UPGRADE_URL,
            plan=plan,
        )
        payload = detail.model_dump()
        # Human-readable message first so clients that stringify `detail` stay useful.
        payload["message"] = (
            f"{dimension.value.replace('_', ' ').title()} limit reached "
            f"({current}/{limit}) on the {plan} plan. Upgrade at {UPGRADE_URL}."
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=payload,
        )

    def record(
        self,
        company_id: UUID,
        dimension: UsageDimension | str,
        quantity: int = 1,
        *,
        agent_id: Optional[UUID] = None,
        api_key_id: Optional[UUID] = None,
        widget_id: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        enforce: bool = False,
        emit_webhook: bool = True,
    ) -> CompanyUsageMeter:
        if isinstance(dimension, str):
            dimension = UsageDimension(dimension)

        if enforce:
            self.check_quota(company_id, dimension, quantity=quantity)

        meter = self.get_or_create_meter(company_id)
        attr = self._counter_attr(dimension)

        if dimension in GAUGE_DIMENSIONS:
            setattr(meter, attr, int(quantity))
        else:
            setattr(meter, attr, int(getattr(meter, attr, 0) or 0) + int(quantity))

        # Keep legacy token counters aligned
        if dimension in (
            UsageDimension.TOTAL_TOKENS,
            UsageDimension.PROMPT_TOKENS,
            UsageDimension.COMPLETION_TOKENS,
        ):
            quota = (
                self.db.query(CompanyQuota)
                .filter(CompanyQuota.company_id == company_id)
                .first()
            )
            if quota:
                quota.current_tokens = int(quota.current_tokens or 0) + int(quantity)

        now = datetime.now(timezone.utc)
        event = UsageEvent(
            company_id=company_id,
            dimension=dimension.value,
            quantity=int(quantity),
            agent_id=agent_id,
            api_key_id=api_key_id,
            widget_id=widget_id,
            source=source,
            metadata_json=metadata or {},
            occurred_at=now,
        )
        self.db.add(event)
        self.repo.save_meter(meter)
        if dimension not in GAUGE_DIMENSIONS:
            self.repo.upsert_daily(company_id, day_floor(now), dimension.value, int(quantity))

        if emit_webhook:
            self._emit_webhook(company_id, "usage.updated", {
                "dimension": dimension.value,
                "quantity": quantity,
                "current": self._current_value(meter, dimension),
            })
        return meter

    def record_ai_usage(
        self,
        company_id: UUID,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        agent_id: Optional[UUID] = None,
        api_key_id: Optional[UUID] = None,
        widget_id: Optional[str] = None,
        source: str = "gateway",
        is_widget: bool = False,
        create_conversation: bool = False,
    ) -> None:
        total = int(prompt_tokens) + int(completion_tokens)
        self.check_quota(company_id, UsageDimension.AI_MESSAGES, quantity=1)
        if total:
            self.check_quota(company_id, UsageDimension.TOTAL_TOKENS, quantity=total)

        kw = dict(
            agent_id=agent_id,
            api_key_id=api_key_id,
            widget_id=widget_id,
            source=source,
            emit_webhook=False,
        )
        self.record(company_id, UsageDimension.AI_MESSAGES, 1, **kw)
        self.record(company_id, UsageDimension.API_REQUESTS, 1, **kw)
        if is_widget:
            self.record(company_id, UsageDimension.WIDGET_REQUESTS, 1, **kw)
        if create_conversation:
            self.record(company_id, UsageDimension.CONVERSATIONS, 1, **kw)
        if prompt_tokens:
            self.record(company_id, UsageDimension.PROMPT_TOKENS, prompt_tokens, **kw)
        if completion_tokens:
            self.record(company_id, UsageDimension.COMPLETION_TOKENS, completion_tokens, **kw)
        if total:
            self.record(company_id, UsageDimension.TOTAL_TOKENS, total, **kw)

        self._emit_webhook(company_id, "usage.updated", {
            "dimension": "ai_messages",
            "quantity": 1,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
        })

    # ── Reset ─────────────────────────────────────────────────────────────────

    def reset_monthly(self, company_id: UUID, *, reason: Optional[str] = None) -> CompanyUsageMeter:
        old = self.get_or_create_meter(company_id)
        plan_key = old.plan_key
        # Force new period by deleting current meter row counters via new period
        # Soft approach: zero counters on current meter
        for dim in UsageDimension:
            if dim in GAUGE_DIMENSIONS:
                continue
            setattr(old, dim.value, 0)
        self.repo.save_meter(old)

        quota = (
            self.db.query(CompanyQuota)
            .filter(CompanyQuota.company_id == company_id)
            .first()
        )
        if quota:
            quota.current_tokens = 0
            quota.current_spend = 0.0
            self.db.commit()

        logger.info(
            "audit_event=usage_reset company_id=%s plan=%s reason=%s",
            company_id,
            plan_key,
            reason,
        )
        return old

    # ── Analytics / dashboard ─────────────────────────────────────────────────

    def _counters(self, meter: CompanyUsageMeter) -> UsageCounters:
        return UsageCounters(
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
        )

    def _limits(self, meter: CompanyUsageMeter) -> UsageLimits:
        return UsageLimits(
            max_agents=meter.max_agents,
            max_messages=meter.max_messages,
            max_tokens=int(meter.max_tokens),
            max_storage=int(meter.max_storage),
            max_domains=meter.max_domains,
            max_team_members=meter.max_team_members,
            max_api_keys=meter.max_api_keys,
            max_templates=meter.max_templates,
        )

    def _progress(self, meter: CompanyUsageMeter) -> list[UsageProgressItem]:
        pairs = [
            ("ai_messages", meter.ai_messages, meter.max_messages),
            ("total_tokens", meter.total_tokens, meter.max_tokens),
            ("storage_bytes", meter.storage_bytes, meter.max_storage),
            ("agents_count", meter.agents_count, meter.max_agents),
            ("api_keys", meter.api_keys, meter.max_api_keys),
            ("domains", meter.domains, meter.max_domains),
            ("active_users", meter.active_users, meter.max_team_members),
            ("templates_published", meter.templates_published, meter.max_templates),
        ]
        out = []
        for dim, cur, lim in pairs:
            lim_i = int(lim or 0)
            cur_i = int(cur or 0)
            pct = round((cur_i / lim_i) * 100, 2) if lim_i > 0 else 0.0
            out.append(UsageProgressItem(dimension=dim, current=cur_i, limit=lim_i, percent=min(pct, 100.0)))
        return out

    def current_usage(self, company_id: UUID) -> CurrentUsageResponse:
        meter = self.get_or_create_meter(company_id)
        return CurrentUsageResponse(
            company_id=company_id,
            plan=meter.plan_key,
            period_type=meter.period_type,
            period_start=meter.period_start,
            period_end=meter.period_end,
            usage=self._counters(meter),
            limits=self._limits(meter),
            progress=self._progress(meter),
            upgrade_url=UPGRADE_URL,
        )

    def history(self, company_id: UUID, days: int = 30, dimension: Optional[str] = None) -> UsageHistoryResponse:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.repo.history(company_id, since=since, dimension=dimension)
        return UsageHistoryResponse(
            company_id=company_id,
            points=[
                UsageHistoryPoint(day=r.day, dimension=r.dimension, quantity=int(r.quantity))
                for r in rows
            ],
        )

    def monthly_summary(self, company_id: UUID) -> MonthlySummaryResponse:
        meter = self.get_or_create_meter(company_id)
        events = self.repo.list_events(company_id, limit=20)
        return MonthlySummaryResponse(
            company_id=company_id,
            plan=meter.plan_key,
            period_start=meter.period_start,
            period_end=meter.period_end,
            usage=self._counters(meter),
            limits=self._limits(meter),
            estimated_monthly_tokens=int(meter.total_tokens or 0),
            recent_events=[
                {
                    "id": str(e.id),
                    "dimension": e.dimension,
                    "quantity": e.quantity,
                    "source": e.source,
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                    "agent_id": str(e.agent_id) if e.agent_id else None,
                    "widget_id": e.widget_id,
                }
                for e in events
            ],
        )

    def dashboard(self, company_id: UUID) -> UsageDashboardResponse:
        current = self.current_usage(company_id)
        summary = self.monthly_summary(company_id)
        since = current.period_start
        return UsageDashboardResponse(
            current=current,
            summary=summary,
            top_agents=self.repo.top_by_metadata(company_id, "agent_id", since=since),
            top_api_keys=self.repo.top_by_metadata(company_id, "api_key_id", since=since),
            top_widgets=self.repo.top_by_metadata(company_id, "widget_id", since=since),
            storage_breakdown={
                "knowledge_upload_bytes": int(summary.usage.knowledge_upload_bytes),
                "storage_bytes": int(summary.usage.storage_bytes),
            },
        )

    def _emit_webhook(self, company_id: UUID, event_type: str, payload: dict) -> None:
        try:
            from app.webhooks.service import WebhookService

            svc = WebhookService(self.db)
            webhooks = svc.repo.get_active_by_company(str(company_id))
            full = {"event": event_type, "data": payload, "company_id": str(company_id)}
            for hook in webhooks:
                types = hook.event_types or []
                if "*" in types or event_type in types:
                    svc._dispatch_worker(hook.url, full, hook.secret)
        except Exception as exc:
            logger.warning("usage webhook emit failed: %s", exc)
