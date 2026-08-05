"""
app/payments/plans/router.py
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.auth.service import AuthService
from app.auth.tenant import require_platform_admin
from app.payments.billing_region import resolve_region_for_company
from app.payments.plans.schema import PlanCreate, PlanUpdate, PlanResponse
from app.payments.plans.service import PlanService
from app.payments.region_pricing import serialize_plan_region_fields

router = APIRouter(prefix="/payments/plans", tags=["Plans"])
_optional_bearer = HTTPBearer(auto_error=False)


def get_plan_service(db: Session = Depends(get_db)) -> PlanService:
    return PlanService(db)


def _to_plan_response(plan, region) -> PlanResponse:
    base = PlanResponse.model_validate(plan)
    return base.model_copy(update=serialize_plan_region_fields(plan, region))


@router.get(
    "",
    response_model=List[PlanResponse],
    summary="List subscription plans",
)
@router.get(
    "/",
    response_model=List[PlanResponse],
    summary="List subscription plans",
)
def list_plans(
    request: Request,
    include_inactive: bool = Query(default=False, description="Platform admin: include inactive"),
    country: Optional[str] = Query(default=None, description="ISO country override for display pricing"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
    service: PlanService = Depends(get_plan_service),
):
    """Public lists active plans; platform admin may request inactive too.

    Response includes region display fields (price_inr/price_usd + display_*).
    """
    company_id = None
    actor = None
    if credentials is not None:
        try:
            actor = AuthService(db).get_current_user_profile(credentials.credentials)
            company_id = actor.company_id
        except Exception:
            actor = None

    if include_inactive:
        if credentials is None or actor is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        require_platform_admin(actor)
        plans = service.list_plans(active_only=False)
    else:
        plans = service.list_plans(active_only=True)

    region = resolve_region_for_company(db, company_id, request, country=country)
    return [_to_plan_response(p, region) for p in plans]


@router.get(
    "/{plan_id:uuid}",
    response_model=PlanResponse,
    summary="Get plan details",
)
def get_plan(
    plan_id: uuid.UUID,
    request: Request,
    country: Optional[str] = Query(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
    service: PlanService = Depends(get_plan_service),
):
    company_id = None
    if credentials is not None:
        try:
            actor = AuthService(db).get_current_user_profile(credentials.credentials)
            company_id = actor.company_id
        except Exception:
            pass
    region = resolve_region_for_company(db, company_id, request, country=country)
    return _to_plan_response(service.get_plan(plan_id), region)


@router.post(
    "/",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create a new plan",
)
def create_plan(
    payload: PlanCreate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PlanService = Depends(get_plan_service),
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
    service: PlanService = Depends(get_plan_service),
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
    service: PlanService = Depends(get_plan_service),
):
    require_platform_admin(current_user)
    return service.deactivate_plan(plan_id)
