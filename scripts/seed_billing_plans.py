"""Seed canonical SaaS plans (Free → Enterprise). Idempotent upsert by name.

Usage:
  python -m scripts.seed_billing_plans
"""
from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session


def seed_billing_plans(db: Session) -> Dict[str, int]:
    """Upsert CANONICAL_PLANS. Caller must ensure ORM mappers are registered."""
    from app.payments.plan_catalog import CANONICAL_PLANS
    from app.payments.plans.model import Plan

    created = updated = 0
    for spec in CANONICAL_PLANS:
        row = db.query(Plan).filter(Plan.name == spec["name"]).first()
        fields = {k: v for k, v in spec.items()}
        # Keep amount aligned with price_usd when present (compat).
        if fields.get("price_usd") is not None and "amount" not in fields:
            fields["amount"] = fields["price_usd"]
        if row:
            for k, v in fields.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            row.is_active = True
            updated += 1
        else:
            db.add(Plan(**{k: v for k, v in fields.items() if hasattr(Plan, k)}, is_active=True))
            created += 1
    db.commit()
    return {"created": created, "updated": updated}


def main() -> None:
    # Same bootstrap as worker / scheduler / seed_marketplace — before Session.
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from app.database.database import SessionLocal

    session = SessionLocal()
    try:
        print(seed_billing_plans(session))
    finally:
        session.close()


if __name__ == "__main__":
    main()
