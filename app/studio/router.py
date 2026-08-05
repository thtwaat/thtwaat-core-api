"""THTWAAT Studio API — /api/v2/studio (Phase 1: save prompts only)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.studio.schemas import (
    StudioProjectCreate,
    StudioProjectListResponse,
    StudioProjectResponse,
)
from app.studio.service import StudioService

router = APIRouter(prefix="/api/v2/studio", tags=["THTWAAT Studio"])


def get_studio_service(db: Session = Depends(get_db)) -> StudioService:
    return StudioService(db)


@router.post(
    "/projects",
    response_model=StudioProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a Studio product prompt (no code generation)",
)
def create_project(
    payload: StudioProjectCreate,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.create(user, payload)


@router.get(
    "/projects",
    response_model=StudioProjectListResponse,
    summary="List Studio projects for the current workspace",
)
def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    items, total = service.list(user, limit=limit, offset=offset)
    return StudioProjectListResponse(
        items=[StudioProjectResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get(
    "/projects/{project_id}",
    response_model=StudioProjectResponse,
    summary="Get a Studio project",
)
def get_project(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get(user, project_id)


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Studio project (owners/admins only)",
)
def delete_project(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    service.delete(user, project_id)
    return None
