"""
app/apps/router.py

FastAPI APIRouter for the Apps module.
Demonstrates integration with the RBAC and Auth modules.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.apps.model import AppStatus
from app.apps.schema import (
    AppCreate,
    AppUpdate,
    AppResponse,
    AppListResponse,
)
from app.apps.service import AppService

# Integration with RBAC & Auth (No modifications to them, just imports)
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission


router = APIRouter(
    prefix="/apps",
    tags=["Apps"],
)

def get_app_service(db: Session = Depends(get_db)) -> AppService:
    return AppService(db)

def check_permission(permission: Permission):
    """
    Combines Auth and RBAC: fetches the current user from the token,
    and passes their role string into the RBAC checker.
    """
    def _check(user: UserProfileResponse = Depends(get_current_user)):
        checker = RequirePermission(permission)
        checker(user.role)
    return _check


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=AppResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new app",
    dependencies=[Depends(check_permission(Permission.APPS_CREATE))]
)
def create_app(
    payload: AppCreate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AppService = Depends(get_app_service),
):
    return service.create_app(payload, actor=current_user)


@router.get(
    "/",
    response_model=AppListResponse,
    summary="List apps",
    dependencies=[Depends(check_permission(Permission.APPS_READ))]
)
def list_apps(
    company_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[AppStatus] = Query(default=None, alias="status"),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AppService = Depends(get_app_service),
):
    return service.list_apps(
        company_id=company_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        actor=current_user,
    )


@router.get(
    "/{app_id}",
    response_model=AppResponse,
    summary="Get app by ID",
    dependencies=[Depends(check_permission(Permission.APPS_READ))]
)
def get_app(
    app_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AppService = Depends(get_app_service),
):
    return service.get_app(app_id, actor=current_user)


@router.patch(
    "/{app_id}",
    response_model=AppResponse,
    summary="Update app",
    dependencies=[Depends(check_permission(Permission.APPS_UPDATE))]
)
def update_app(
    app_id: uuid.UUID,
    payload: AppUpdate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AppService = Depends(get_app_service),
):
    return service.update_app(app_id, payload, actor=current_user)


@router.delete(
    "/{app_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft-delete app",
    dependencies=[Depends(check_permission(Permission.APPS_DELETE))]
)
def delete_app(
    app_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AppService = Depends(get_app_service),
):
    return service.delete_app(app_id, actor=current_user)
