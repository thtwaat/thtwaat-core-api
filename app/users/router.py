"""
app/users/router.py

FastAPI APIRouter for the Users module.
Delegates all business logic to UserService.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.auth.service import AuthService
from app.users.model import UserStatus
from app.users.schema import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
)
from app.users.service import UserService


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

# Optional bearer — public signup stays unauthenticated; platform admins may
# pass Authorization to create privileged roles.
_optional_bearer = HTTPBearer(auto_error=False)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """FastAPI dependency — provides a UserService with a DB session."""
    return UserService(db)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
):
    """
    Create a new user account within a specific company.

    Public signup allows only ``company_owner`` / ``employee``.
    Authenticated platform admins may assign any role.
    """
    actor: Optional[UserProfileResponse] = None
    if credentials is not None:
        actor = AuthService(db).get_current_user_profile(credentials.credentials)
    return service.create_user(payload, actor=actor)


@router.get(
    "/",
    response_model=UserListResponse,
    summary="List users",
)
def list_users(
    company_id: Optional[uuid.UUID] = Query(default=None, description="Filter by company"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[UserStatus] = Query(default=None, alias="status"),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """
    Retrieve a paginated list of users.
    Scoped to the caller's company unless platform admin.
    """
    return service.list_users(
        company_id=company_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        actor=current_user,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
def get_user(
    user_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Retrieve a single user by their UUID (tenant-scoped)."""
    return service.get_user(user_id, actor=current_user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user details",
)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Partially update user information (name, email, role, etc.)."""
    return service.update_user(user_id, payload, actor=current_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate (soft-delete) a user",
)
def deactivate_user(
    user_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """
    Soft-delete a user — marks them as inactive.
    """
    return service.deactivate_user(user_id, actor=current_user)
