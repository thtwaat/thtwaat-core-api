"""
app/payments/plans/router.py
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.auth.service import AuthService
from app.auth.tenant import require_platform_admin
from app.payments.plans.schema import PlanCreate, PlanUpdate, PlanResponse
from app.payments.plans.service import PlanService

router = APIRouter(prefix="/payments/plans", tags=["Plans"])
_optional_bearer = HTTPBearer(auto_error=False)


def get_plan_service(db: Session = Depends(get_db)) -> PlanService:
    return PlanService(db)


@router.get(
    "",
    response_model=List[PlanResponse],
    summary="List subscription plans",
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=List[PlanResponse],
    summary="List subscription plans",
)
def list_plans(
    include_inactive: bool = Query(default=False, description="Platform admin: include inactive"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
    service: PlanService = Depends(get_plan_service),
):
    """Public lists active plans; platform admin may request inactive too."""
    if include_inactive:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        actor = AuthService(db).get_current_user_profile(credentials.credentials)
        require_platform_admin(actor)
        return service.list_plans(active_only=False)
    return service.list_plans(active_only=True)


@router.get(
    "/{plan_id:uuid}",
    response_model=PlanResponse,
    summary="Get plan details",
)
def get_plan(
    plan_id: uuid.UUID,
    service: PlanService = Depends(get_plan_service)
):
    return service.get_plan(plan_id)


@router.post(
    "/",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create a new plan",
)
def create_plan(
    payload: PlanCreate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PlanService = Depends(get_plan_service)
):
    """Platform admin only — creates a new billing plan."""
    require_platform_admin(current_user)
    return service.create_plan(payload)


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="[Admin] Update a plan",
)
def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PlanService = Depends(get_plan_service)
):
    require_platform_admin(current_user)
    return service.update_plan(plan_id, payload)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_200_OK,
    summary="[Admin] Deactivate a plan",
)
def deactivate_plan(
    plan_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PlanService = Depends(get_plan_service)
):
    require_platform_admin(current_user)
    return service.deactivate_plan(plan_id)
