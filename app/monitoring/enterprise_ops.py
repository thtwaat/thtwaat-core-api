"""Enterprise Admin Analytics & Operations — additive facade over existing modules."""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase
from app.agent_platform.models.agent import AgentConfig
from app.companies.model import Company
from app.monitoring.exports import export_payload
from app.openai_compat.models import OpenAICompletionLog
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.plans.model import Plan
from app.payments.subscriptions.model import Subscription, SubscriptionStatus
from app.usage.models import CompanyUsageMeter
from app.users.model import User, UserStatus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _period_start(days: int = 30) -> datetime:
    return _now() - timedelta(days=days)


class EnterpriseOpsService:
    """Platform-wide analytics, workspace ops detail, unified logs, exports."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Executive dashboard ───────────────────────────────────────────────────

    def executive_dashboard(self) -> Dict[str, Any]:
        now = _now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        workspaces = int(
            self.db.scalar(select(func.count(Company.id)).where(Company.is_active.is_(True))) or 0
        )
        active_users = int(
            self.db.scalar(
                select(func.count(User.id)).where(
                    User.is_active.is_(True),
                    User.status == UserStatus.ACTIVE,
                )
            )
            or 0
        )
        new_signups = int(
            self.db.scalar(select(func.count(User.id)).where(User.created_at >= week_ago)) or 0
        )
        active_agents = int(
            self.db.scalar(
                select(func.count(AgentConfig.id)).where(AgentConfig.status == "PUBLISHED")
            )
            or 0
        )
        knowledge_bases = int(self.db.scalar(select(func.count(KnowledgeBase.id))) or 0)

        # Widgets: published agents act as embeddable widget surfaces
        widgets = active_agents

        meter_ai = self.db.execute(
            select(
                func.coalesce(func.sum(CompanyUsageMeter.ai_messages), 0),
                func.coalesce(func.sum(CompanyUsageMeter.total_tokens), 0),
                func.coalesce(func.sum(CompanyUsageMeter.api_requests), 0),
                func.coalesce(func.sum(CompanyUsageMeter.estimated_cost), 0),
            ).where(CompanyUsageMeter.period_type == "monthly")
        ).one()
        ai_requests = int(meter_ai[0] or 0)
        token_usage = int(meter_ai[1] or 0)
        api_usage = int(meter_ai[2] or 0)
        ai_cost = float(meter_ai[3] or 0)

        # Completion-log fallback for AI request volume when meters empty
        if ai_requests == 0:
            ai_requests = int(
                self.db.scalar(
                    select(func.count(OpenAICompletionLog.id)).where(
                        OpenAICompletionLog.created_at >= month_ago
                    )
                )
                or 0
            )
        if token_usage == 0:
            token_usage = int(
                self.db.scalar(
                    select(func.coalesce(func.sum(OpenAICompletionLog.total_tokens), 0)).where(
                        OpenAICompletionLog.created_at >= month_ago
                    )
                )
                or 0
            )

        billing = self._billing_kpis()
        churn = self._churn_rate(month_ago)
        conversion = self._conversion_rate()

        return {
            "generated_at": now,
            "workspaces": workspaces,
            "active_users": active_users,
            "new_signups": new_signups,
            "active_agents": active_agents,
            "knowledge_bases": knowledge_bases,
            "widgets": widgets,
            "ai_requests": ai_requests,
            "token_usage": token_usage,
            "api_usage": api_usage,
            "ai_cost": ai_cost,
            "revenue": billing["revenue"],
            "mrr": billing["mrr"],
            "arr": billing["arr"],
            "active_subscriptions": billing["active_subscriptions"],
            "churn": churn,
            "conversion_rate": conversion,
            "signups_24h": int(
                self.db.scalar(select(func.count(User.id)).where(User.created_at >= day_ago)) or 0
            ),
            "signups_7d": new_signups,
            "signups_30d": int(
                self.db.scalar(select(func.count(User.id)).where(User.created_at >= month_ago)) or 0
            ),
        }

    def _billing_kpis(self) -> Dict[str, Any]:
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
        mrr = Decimal("0")
        for sub in subs:
            plan = self.db.get(Plan, sub.plan_id)
            if not plan:
                continue
            amount = Decimal(str(plan.amount or 0))
            if (plan.interval or "month").lower() == "year":
                amount = amount / Decimal("12")
            mrr += amount
        paid = (
            self.db.scalar(
                select(func.coalesce(func.sum(Invoice.amount_paid), 0)).where(
                    Invoice.status == InvoiceStatus.PAID
                )
            )
            or 0
        )
        return {
            "mrr": float(mrr),
            "arr": float(mrr * Decimal("12")),
            "revenue": float(paid),
            "active_subscriptions": len(subs),
        }

    def _churn_rate(self, since: datetime) -> float:
        cancelled = int(
            self.db.scalar(
                select(func.count(Subscription.id)).where(
                    Subscription.status == SubscriptionStatus.CANCELLED,
                    Subscription.updated_at >= since,
                )
            )
            or 0
        )
        base = int(
            self.db.scalar(select(func.count(Subscription.id)).where(Subscription.created_at < since))
            or 0
        )
        if base <= 0:
            return 0.0
        return round((cancelled / base) * 100.0, 2)

    def _conversion_rate(self) -> float:
        from app.companies.model import CompanyPlan

        total_active = int(
            self.db.scalar(select(func.count(Company.id)).where(Company.is_active.is_(True))) or 0
        )
        paid = int(
            self.db.scalar(
                select(func.count(Company.id)).where(
                    Company.is_active.is_(True),
                    Company.plan != CompanyPlan.FREE,
                )
            )
            or 0
        )
        if total_active <= 0:
            return 0.0
        return round((paid / total_active) * 100.0, 2)

    # ── AI analytics ──────────────────────────────────────────────────────────

    def ai_analytics(self, days: int = 30) -> Dict[str, Any]:
        days = max(1, min(days, 90))
        since = _period_start(days)
        now = _now()

        logs = (
            self.db.query(OpenAICompletionLog)
            .filter(OpenAICompletionLog.created_at >= since)
            .order_by(OpenAICompletionLog.created_at.asc())
            .limit(50_000)
            .all()
        )

        by_hour: Dict[str, int] = {}
        by_day: Dict[str, int] = {}
        by_month: Dict[str, int] = {}
        by_provider: Dict[str, Dict[str, Any]] = {}
        latency_sum = 0
        latency_n = 0
        success = 0
        errors = 0
        prompt_counts: Dict[str, int] = {}
        agent_counts: Dict[str, int] = {}
        tokens_in = 0
        tokens_out = 0

        for row in logs:
            ts = row.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            day_key = ts.strftime("%Y-%m-%d")
            month_key = ts.strftime("%Y-%m")
            by_hour[hour_key] = by_hour.get(hour_key, 0) + 1
            by_day[day_key] = by_day.get(day_key, 0) + 1
            by_month[month_key] = by_month.get(month_key, 0) + 1

            provider = (row.provider or "unknown").lower()
            bucket = by_provider.setdefault(
                provider,
                {"requests": 0, "tokens": 0, "cost_estimate": 0.0, "errors": 0, "latency_ms": 0.0},
            )
            bucket["requests"] += 1
            bucket["tokens"] += int(row.total_tokens or 0)
            # Rough cost heuristic ($/1M tokens) — display only
            rate = {"openai": 5.0, "anthropic": 8.0, "gemini": 2.0, "openrouter": 3.0, "ollama": 0.0}.get(
                provider, 4.0
            )
            cost = (int(row.total_tokens or 0) / 1_000_000.0) * rate
            bucket["cost_estimate"] = float(bucket["cost_estimate"]) + cost
            bucket["latency_ms"] = float(bucket["latency_ms"]) + float(row.latency_ms or 0)

            tokens_in += int(row.prompt_tokens or 0)
            tokens_out += int(row.completion_tokens or 0)
            latency_sum += int(row.latency_ms or 0)
            latency_n += 1

            status = (row.status or "").lower()
            if status in ("succeeded", "success", "ok", "completed"):
                success += 1
            else:
                errors += 1
                bucket["errors"] += 1

            # Top prompts — first user message snippet
            msgs = row.request_messages or []
            snippet = ""
            if isinstance(msgs, list):
                for m in msgs:
                    if isinstance(m, dict) and m.get("role") == "user":
                        content = m.get("content")
                        if isinstance(content, str):
                            snippet = content.strip()[:120]
                        elif isinstance(content, list):
                            snippet = str(content)[:120]
                        break
            if snippet:
                prompt_counts[snippet] = prompt_counts.get(snippet, 0) + 1

            if row.agent_id:
                key = str(row.agent_id)
                agent_counts[key] = agent_counts.get(key, 0) + 1

        total = success + errors
        for p, bucket in by_provider.items():
            n = int(bucket["requests"] or 1)
            bucket["avg_latency_ms"] = round(float(bucket["latency_ms"]) / n, 2)
            bucket["cost_estimate"] = round(float(bucket["cost_estimate"]), 4)
            del bucket["latency_ms"]

        top_prompts = sorted(prompt_counts.items(), key=lambda x: -x[1])[:20]
        top_agents = sorted(agent_counts.items(), key=lambda x: -x[1])[:20]

        return {
            "generated_at": now,
            "range_start": since,
            "range_end": now,
            "days": days,
            "requests_hour": [{"t": k, "count": v} for k, v in sorted(by_hour.items())[-48:]],
            "requests_day": [{"t": k, "count": v} for k, v in sorted(by_day.items())],
            "requests_month": [{"t": k, "count": v} for k, v in sorted(by_month.items())],
            "provider_usage": [
                {"provider": k, **v} for k, v in sorted(by_provider.items(), key=lambda x: -x[1]["requests"])
            ],
            "token_usage": {
                "prompt_tokens": tokens_in,
                "completion_tokens": tokens_out,
                "total_tokens": tokens_in + tokens_out,
            },
            "cost_by_provider": [
                {"provider": k, "cost": v["cost_estimate"]}
                for k, v in sorted(by_provider.items(), key=lambda x: -float(x[1]["cost_estimate"]))
            ],
            "latency": {
                "avg_ms": round(latency_sum / latency_n, 2) if latency_n else 0.0,
                "samples": latency_n,
            },
            "error_rate": round((errors / total) * 100.0, 2) if total else 0.0,
            "success_rate": round((success / total) * 100.0, 2) if total else 100.0,
            "top_prompts": [{"prompt": p, "count": c} for p, c in top_prompts],
            "top_agents": [{"agent_id": a, "count": c} for a, c in top_agents],
            "total_requests": total,
        }

    # ── Workspace ops detail ──────────────────────────────────────────────────

    def workspace_ops(self, company_id: UUID) -> Dict[str, Any]:
        company = self.db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Workspace not found")

        meter = (
            self.db.query(CompanyUsageMeter)
            .filter(
                CompanyUsageMeter.company_id == company_id,
                CompanyUsageMeter.period_type == "monthly",
            )
            .order_by(CompanyUsageMeter.period_start.desc())
            .first()
        )
        sub = (
            self.db.query(Subscription)
            .filter(
                Subscription.company_id == company_id,
                Subscription.status.in_(
                    [
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING,
                        SubscriptionStatus.PAST_DUE,
                        SubscriptionStatus.CANCELLED,
                    ]
                ),
            )
            .order_by(Subscription.created_at.desc())
            .first()
        )
        plan = self.db.get(Plan, sub.plan_id) if sub else None

        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.company_id == company_id)
            .order_by(Invoice.created_at.desc())
            .limit(20)
            .all()
        )
        ai_recent = (
            self.db.query(OpenAICompletionLog)
            .filter(OpenAICompletionLog.company_id == company_id)
            .order_by(OpenAICompletionLog.created_at.desc())
            .limit(20)
            .all()
        )

        quotas = {}
        usage = {}
        remaining = {}
        if meter:
            quotas = {
                "max_agents": meter.max_agents,
                "max_messages": meter.max_messages,
                "max_tokens": meter.max_tokens,
                "max_storage": meter.max_storage,
                "max_api_keys": meter.max_api_keys,
                "max_team_members": meter.max_team_members,
            }
            usage = {
                "ai_messages": meter.ai_messages,
                "total_tokens": meter.total_tokens,
                "api_requests": meter.api_requests,
                "storage_bytes": meter.storage_bytes,
                "estimated_cost": float(meter.estimated_cost or 0),
            }
            remaining = {
                "messages": max(0, int(meter.max_messages) - int(meter.ai_messages or 0)),
                "tokens": max(0, int(meter.max_tokens) - int(meter.total_tokens or 0)),
                "storage": max(0, int(meter.max_storage) - int(meter.storage_bytes or 0)),
            }

        return {
            "company": {
                "id": str(company.id),
                "name": company.name,
                "slug": company.slug,
                "plan": company.plan.value if hasattr(company.plan, "value") else str(company.plan),
                "status": company.status.value if hasattr(company.status, "value") else str(company.status),
                "is_active": company.is_active,
            },
            "quotas": quotas,
            "usage": usage,
            "remaining_quota": remaining,
            "billing": {
                "subscription_status": (
                    sub.status.value if sub and hasattr(sub.status, "value") else (str(sub.status) if sub else None)
                ),
                "plan_name": plan.name if plan else None,
                "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)) if sub else False,
                "invoices": [
                    {
                        "id": str(inv.id),
                        "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                        "amount_paid": float(inv.amount_paid or 0),
                        "amount_due": float(inv.amount_due or 0),
                        "created_at": inv.created_at.isoformat() if inv.created_at else None,
                    }
                    for inv in invoices
                ],
            },
            "ai_usage": [
                {
                    "id": str(r.id),
                    "model": r.model,
                    "provider": r.provider,
                    "total_tokens": r.total_tokens,
                    "latency_ms": r.latency_ms,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in ai_recent
            ],
            "api_usage": {
                "api_requests": usage.get("api_requests", 0),
                "ai_messages": usage.get("ai_messages", 0),
            },
        }

    # ── Unified logs ──────────────────────────────────────────────────────────

    def unified_logs(
        self,
        *,
        category: str = "all",
        limit: int = 50,
        company_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        limit = max(1, min(limit, 200))
        cat = (category or "all").lower()
        items: List[Dict[str, Any]] = []

        if cat in ("all", "audit"):
            items.extend(self._audit_logs(limit, company_id))
        if cat in ("all", "payment", "payments"):
            items.extend(self._payment_logs(limit, company_id))
        if cat in ("all", "webhook", "webhooks"):
            items.extend(self._webhook_logs(limit))
        if cat in ("all", "auth", "authentication"):
            items.extend(self._auth_logs(limit, company_id))
        if cat in ("all", "ai"):
            items.extend(self._ai_logs(limit, company_id))

        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {
            "category": cat,
            "total": len(items[:limit]),
            "items": items[:limit],
            "generated_at": _now(),
        }

    def _audit_logs(self, limit: int, company_id: Optional[UUID]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            from app.monitoring.models import OpsAdminActivity

            q = self.db.query(OpsAdminActivity).order_by(OpsAdminActivity.created_at.desc()).limit(limit)
            for row in q.all():
                out.append(
                    {
                        "category": "audit",
                        "action": row.action,
                        "resource_type": row.resource_type,
                        "resource_id": row.resource_id,
                        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                        "details": row.details or {},
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
        except Exception as exc:
            logger.debug("ops admin activity unavailable: %s", exc)
        try:
            from app.enterprise.models import EnterpriseAuditLog

            q = self.db.query(EnterpriseAuditLog).order_by(EnterpriseAuditLog.created_at.desc()).limit(limit)
            if company_id:
                q = q.filter(EnterpriseAuditLog.company_id == company_id)
            for row in q.all():
                out.append(
                    {
                        "category": "audit",
                        "action": getattr(row, "action", None) or getattr(row, "event_type", "audit"),
                        "resource_type": getattr(row, "resource_type", None),
                        "resource_id": str(getattr(row, "resource_id", "") or ""),
                        "actor_user_id": str(row.actor_user_id) if getattr(row, "actor_user_id", None) else None,
                        "details": getattr(row, "details", None) or getattr(row, "metadata_json", {}) or {},
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
        except Exception as exc:
            logger.debug("enterprise audit unavailable: %s", exc)
        return out

    def _payment_logs(self, limit: int, company_id: Optional[UUID]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            from app.payments.model import Payment

            q = self.db.query(Payment).order_by(Payment.created_at.desc()).limit(limit)
            if company_id:
                q = q.filter(Payment.company_id == company_id)
            for row in q.all():
                out.append(
                    {
                        "category": "payment",
                        "action": str(getattr(row.status, "value", row.status)),
                        "resource_type": "payment",
                        "resource_id": str(row.id),
                        "actor_user_id": None,
                        "details": {
                            "amount": float(row.amount or 0),
                            "provider": getattr(row, "provider", None),
                            "company_id": str(row.company_id) if row.company_id else None,
                        },
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
        except Exception as exc:
            logger.debug("payment logs unavailable: %s", exc)
        q = self.db.query(Invoice).order_by(Invoice.created_at.desc()).limit(limit)
        if company_id:
            q = q.filter(Invoice.company_id == company_id)
        for inv in q.all():
            out.append(
                {
                    "category": "payment",
                    "action": f"invoice_{inv.status.value if hasattr(inv.status, 'value') else inv.status}",
                    "resource_type": "invoice",
                    "resource_id": str(inv.id),
                    "actor_user_id": None,
                    "details": {
                        "amount_paid": float(inv.amount_paid or 0),
                        "company_id": str(inv.company_id),
                    },
                    "created_at": inv.created_at.isoformat() if inv.created_at else None,
                }
            )
        return out

    def _webhook_logs(self, limit: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            from app.payments.billing_extras import BillingWebhookEvent

            rows = (
                self.db.query(BillingWebhookEvent)
                .order_by(BillingWebhookEvent.created_at.desc())
                .limit(limit)
                .all()
            )
            for row in rows:
                out.append(
                    {
                        "category": "webhook",
                        "action": row.event_type,
                        "resource_type": "billing_webhook",
                        "resource_id": row.event_id,
                        "actor_user_id": None,
                        "details": {
                            "provider": row.provider,
                            "processed": bool(row.processed),
                        },
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
        except Exception as exc:
            logger.debug("billing webhook logs unavailable: %s", exc)
        try:
            from app.webhooks.models import WebhookDelivery

            rows = (
                self.db.query(WebhookDelivery)
                .order_by(WebhookDelivery.created_at.desc())
                .limit(limit)
                .all()
            )
            for row in rows:
                out.append(
                    {
                        "category": "webhook",
                        "action": getattr(row, "event", None) or getattr(row, "status", "delivery"),
                        "resource_type": "webhook_delivery",
                        "resource_id": str(row.id),
                        "actor_user_id": None,
                        "details": {
                            "status": getattr(row, "status", None),
                            "attempts": getattr(row, "attempts", None),
                            "last_error": getattr(row, "last_error", None),
                        },
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
        except Exception as exc:
            logger.debug("webhook delivery logs unavailable: %s", exc)
        return out

    def _auth_logs(self, limit: int, company_id: Optional[UUID]) -> List[Dict[str, Any]]:
        """Auth activity derived from enterprise audit + recent user status changes."""
        out: List[Dict[str, Any]] = []
        try:
            from app.enterprise.models import EnterpriseAuditLog

            q = (
                self.db.query(EnterpriseAuditLog)
                .order_by(EnterpriseAuditLog.created_at.desc())
                .limit(limit * 2)
            )
            if company_id:
                q = q.filter(EnterpriseAuditLog.company_id == company_id)
            for row in q.all():
                action = str(getattr(row, "action", "") or getattr(row, "event_type", "")).lower()
                if not any(k in action for k in ("login", "auth", "otp", "password", "session")):
                    continue
                out.append(
                    {
                        "category": "auth",
                        "action": action,
                        "resource_type": "user",
                        "resource_id": str(getattr(row, "resource_id", "") or ""),
                        "actor_user_id": str(row.actor_user_id) if getattr(row, "actor_user_id", None) else None,
                        "details": getattr(row, "details", None) or {},
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
                if len(out) >= limit:
                    break
        except Exception as exc:
            logger.debug("auth logs unavailable: %s", exc)
        return out

    def _ai_logs(self, limit: int, company_id: Optional[UUID]) -> List[Dict[str, Any]]:
        q = self.db.query(OpenAICompletionLog).order_by(OpenAICompletionLog.created_at.desc()).limit(limit)
        if company_id:
            q = q.filter(OpenAICompletionLog.company_id == company_id)
        return [
            {
                "category": "ai",
                "action": row.status,
                "resource_type": "completion",
                "resource_id": row.completion_id,
                "actor_user_id": None,
                "details": {
                    "model": row.model,
                    "provider": row.provider,
                    "tokens": row.total_tokens,
                    "latency_ms": row.latency_ms,
                    "company_id": str(row.company_id),
                    "error": row.error_detail,
                },
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in q.all()
        ]

    # ── Marketplace analytics (platform rollup) ───────────────────────────────

    def marketplace_ops_analytics(self, days: int = 30) -> Dict[str, Any]:
        days = max(1, min(days, 90))
        out: Dict[str, Any] = {"generated_at": _now(), "days": days}
        try:
            from app.marketplace.analytics import catalog_analytics

            catalog = catalog_analytics(self.db, days=days)
            out["catalog"] = catalog.model_dump() if hasattr(catalog, "model_dump") else catalog
        except Exception as exc:
            logger.warning("catalog analytics unavailable: %s", exc)
        try:
            from app.agent_store.service import AgentStoreService

            stats = AgentStoreService(self.db).admin_stats()
            out["store"] = stats.model_dump() if hasattr(stats, "model_dump") else stats
        except Exception as exc:
            logger.warning("agent store stats unavailable: %s", exc)
        return out

    # ── User admin helpers ────────────────────────────────────────────────────

    def invite_user(
        self,
        *,
        actor_id: UUID,
        email: str,
        company_id: UUID,
        role: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.auth.schema import UserProfileResponse
        from app.rbac.enums import EnterpriseRole
        from app.users.schema import UserCreate
        from app.users.service import UserService

        company = self.db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        temp_password = _temp_password()
        try:
            role_enum = EnterpriseRole(role)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}") from exc

        actor = self.db.get(User, actor_id)
        if not actor:
            raise HTTPException(status_code=404, detail="Actor not found")
        actor_profile = UserProfileResponse(
            id=actor.id,
            company_id=actor.company_id,
            email=actor.email,
            first_name=actor.first_name,
            last_name=actor.last_name,
            role=actor.role.value if hasattr(actor.role, "value") else str(actor.role),
        )

        local = email.split("@")[0]
        payload = UserCreate(
            email=email.strip().lower(),
            password=temp_password,
            first_name=(first_name or local)[:100],
            last_name=(last_name or "User")[:100],
            company_id=company_id,
            role=role_enum,
        )
        user = UserService(self.db).create_user(payload, actor=actor_profile)
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                "company_id": str(user.company_id),
            },
            "temporary_password": temp_password,
            "note": "Share the temporary password securely; user should change it after login.",
        }

    def admin_reset_password(self, *, actor_id: UUID, user_id: UUID) -> Dict[str, Any]:
        from app.users.service import UserService

        user = self.db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        temp_password = _temp_password()
        svc = UserService(self.db)
        user.hashed_password = svc._hash_password(temp_password)
        self.db.add(user)
        self.db.commit()
        return {
            "user_id": str(user.id),
            "email": user.email,
            "temporary_password": temp_password,
            "reset_by": str(actor_id),
            "note": "Temporary password issued by platform admin.",
        }

    # ── Exports ───────────────────────────────────────────────────────────────

    def export_dataset(self, kind: str, format: str = "csv") -> Dict[str, Any]:
        kind_l = (kind or "").lower()
        if kind_l in ("executive", "dashboard"):
            data = self.executive_dashboard()
            headers = list(data.keys())
            rows = [[data.get(h) for h in headers]]
            title = "executive-dashboard"
        elif kind_l in ("ai", "ai-analytics"):
            data = self.ai_analytics()
            headers = ["provider", "requests", "tokens", "cost_estimate", "errors", "avg_latency_ms"]
            rows = [
                [
                    p.get("provider"),
                    p.get("requests"),
                    p.get("tokens"),
                    p.get("cost_estimate"),
                    p.get("errors"),
                    p.get("avg_latency_ms"),
                ]
                for p in data.get("provider_usage") or []
            ]
            title = "ai-analytics"
        elif kind_l in ("logs", "audit"):
            data = self.unified_logs(category="all", limit=200)
            headers = ["category", "action", "resource_type", "resource_id", "created_at"]
            rows = [
                [i.get("category"), i.get("action"), i.get("resource_type"), i.get("resource_id"), i.get("created_at")]
                for i in data.get("items") or []
            ]
            title = "admin-logs"
        elif kind_l in ("workspaces", "companies"):
            companies = self.db.query(Company).order_by(Company.created_at.desc()).limit(500).all()
            headers = ["id", "name", "slug", "plan", "status", "is_active"]
            rows = [
                [
                    str(c.id),
                    c.name,
                    c.slug,
                    c.plan.value if hasattr(c.plan, "value") else str(c.plan),
                    c.status.value if hasattr(c.status, "value") else str(c.status),
                    c.is_active,
                ]
                for c in companies
            ]
            title = "workspaces"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown export kind: {kind}")

        try:
            return export_payload(format=format, title=title, headers=headers, rows=rows)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


def _temp_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
