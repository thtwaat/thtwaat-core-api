"""
app/payments/plans/service.py

Business logic for Plans.
"""
import uuid
import logging
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.payments.plans.model import Plan
from app.payments.plans.schema import PlanCreate, PlanUpdate
from app.payments.plans.repository import PlanRepository

logger = logging.getLogger(__name__)


class PlanService:
    def __init__(self, db: Session):
        self.repo = PlanRepository(db)

    def create_plan(self, data: PlanCreate) -> Plan:
        if self.repo.get_by_name(data.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Plan '{data.name}' already exists."
            )
        return self.repo.create(data.model_dump())

    def list_plans(self, active_only: bool = True) -> List[Plan]:
        return self.repo.list_active() if active_only else self.repo.list_all()

    def get_plan(self, plan_id: uuid.UUID) -> Plan:
        plan = self.repo.get_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found.")
        return plan

    def update_plan(self, plan_id: uuid.UUID, data: PlanUpdate) -> Plan:
        plan = self.get_plan(plan_id)
        return self.repo.update(plan, data.model_dump(exclude_unset=True))

    def deactivate_plan(self, plan_id: uuid.UUID) -> dict:
        plan = self.get_plan(plan_id)
        self.repo.deactivate(plan)
        return {"detail": f"Plan '{plan.name}' has been deactivated."}
