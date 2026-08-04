"""Admin billing analytics (MRR/ARR/revenue) — additive under /payments/admin."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.payments.invoices.model import Invoice, InvoiceStatus
from app.payments.plans.model import Plan
from app.payments.provider_flags import billing_providers_status
from app.payments.subscriptions.model import Subscription, SubscriptionStatus
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission
from app.usage.models import CompanyUsageMeter

router = APIRouter(prefix="/payments/admin", tags=["Billing Admin"])


def require_platform_admin(user: UserProfileResponse = Depends(get_current_user)):
    RequirePermission(Permission.PLATFORM_ADMIN)(user.role)
    return user


@router.get("/providers")
def admin_billing_providers(
    _: UserProfileResponse = Depends(require_platform_admin),
):
    return billing_providers_status()


@router.get("/analytics")
def admin_billing_analytics(
    _: UserProfileResponse = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """MRR / ARR / revenue / refunds / failed / top customers & plans / AI costs."""
    active_statuses = [
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.PAST_DUE,
    ]
    subs = (
        db.query(Subscription)
        .filter(Subscription.status.in_(active_statuses))
        .all()
    )
    plan_cache: Dict[Any, Plan] = {}
    mrr = Decimal("0")
    plan_counts: Dict[str, int] = {}
    for sub in subs:
        plan = plan_cache.get(sub.plan_id)
        if plan is None:
            plan = db.get(Plan, sub.plan_id)
            plan_cache[sub.plan_id] = plan
        if not plan:
            continue
        amount = Decimal(str(plan.amount or 0))
        if (plan.interval or "month").lower() == "year":
            amount = amount / Decimal("12")
        mrr += amount
        key = plan.name
        plan_counts[key] = plan_counts.get(key, 0) + 1

    paid = (
        db.query(func.coalesce(func.sum(Invoice.amount_paid), 0))
        .filter(Invoice.status == InvoiceStatus.PAID)
        .scalar()
    )
    revenue = float(paid or 0)

    # Refunds / failed — best-effort from payments table when present
    refunds = 0.0
    failed_payments = 0
    try:
        from app.payments.model import Payment, PaymentStatus

        refunds = float(
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.status == PaymentStatus.REFUNDED)
            .scalar()
            or 0
        )
        failed_payments = int(
            db.query(func.count(Payment.id))
            .filter(Payment.status == PaymentStatus.FAILED)
            .scalar()
            or 0
        )
    except Exception:
        pass

    top_customers: List[Dict[str, Any]] = []
    rows = (
        db.query(Invoice.company_id, func.sum(Invoice.amount_paid).label("total"))
        .filter(Invoice.status == InvoiceStatus.PAID)
        .group_by(Invoice.company_id)
        .order_by(func.sum(Invoice.amount_paid).desc())
        .limit(10)
        .all()
    )
    for company_id, total in rows:
        top_customers.append(
            {"company_id": str(company_id), "revenue": float(total or 0)}
        )

    top_plans = [
        {"plan": name, "active_subscriptions": count}
        for name, count in sorted(plan_counts.items(), key=lambda x: -x[1])
    ]

    token_usage = int(
        db.query(func.coalesce(func.sum(CompanyUsageMeter.total_tokens), 0)).scalar() or 0
    )
    ai_costs = 0.0
    try:
        ai_costs = float(
            db.query(func.coalesce(func.sum(CompanyUsageMeter.estimated_cost), 0)).scalar()
            or 0
        )
    except Exception:
        ai_costs = 0.0

    gross_margin = round(revenue - ai_costs, 2)
    arr = float(mrr * Decimal("12"))

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "mrr": float(mrr),
        "arr": arr,
        "revenue": revenue,
        "refunds": refunds,
        "failed_payments": failed_payments,
        "active_subscriptions": len(subs),
        "top_customers": top_customers,
        "top_plans": top_plans,
        "token_usage": token_usage,
        "ai_costs": ai_costs,
        "gross_margin": gross_margin,
        "providers": billing_providers_status(),
    }
