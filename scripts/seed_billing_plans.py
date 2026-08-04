"""Seed canonical SaaS plans (Free → Enterprise). Idempotent upsert by name."""
from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session

from app.payments.plan_catalog import CANONICAL_PLANS
from app.payments.plans.model import Plan


def seed_billing_plans(db: Session) -> Dict[str, int]:
    created = updated = 0
    for spec in CANONICAL_PLANS:
        row = db.query(Plan).filter(Plan.name == spec["name"]).first()
        fields = {k: v for k, v in spec.items()}
        if row:
            for k, v in fields.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            row.is_active = True
            updated += 1
        else:
            db.add(Plan(**fields, is_active=True))
            created += 1
    db.commit()
    return {"created": created, "updated": updated}


if __name__ == "__main__":
    from app.database.database import SessionLocal

    session = SessionLocal()
    try:
        print(seed_billing_plans(session))
    finally:
        session.close()
