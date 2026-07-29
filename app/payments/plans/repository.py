"""
app/payments/plans/repository.py
"""
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.payments.plans.model import Plan


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Plan:
        plan = Plan(**data)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get_by_id(self, plan_id: uuid.UUID) -> Optional[Plan]:
        return self.db.execute(
            select(Plan).where(Plan.id == plan_id)
        ).scalar_one_or_none()

    def get_by_name(self, name: str) -> Optional[Plan]:
        return self.db.execute(
            select(Plan).where(Plan.name == name)
        ).scalar_one_or_none()

    def list_active(self) -> List[Plan]:
        return list(self.db.execute(
            select(Plan).where(Plan.is_active == True).order_by(Plan.amount.asc())
        ).scalars().all())

    def list_all(self) -> List[Plan]:
        return list(self.db.execute(
            select(Plan).order_by(Plan.amount.asc())
        ).scalars().all())

    def update(self, plan: Plan, data: dict) -> Plan:
        for key, value in data.items():
            setattr(plan, key, value)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def deactivate(self, plan: Plan) -> Plan:
        plan.is_active = False
        self.db.commit()
        self.db.refresh(plan)
        return plan
