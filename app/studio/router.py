"""THTWAAT Studio API — /api/v2/studio (prompts + AI Product Architect)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.studio.schemas import (
    StudioAnalyzeResponse,
    StudioBlueprintResponse,
    StudioBlueprintUpdate,
    StudioBlueprintVersionList,
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


@router.post(
    "/projects/{project_id}/analyze",
    response_model=StudioAnalyzeResponse,
    summary="Analyze prompt into a Product Blueprint (no code generation)",
)
async def analyze_project(
    project_id: UUID,
    use_ai: bool = Query(True, description="Try AI Gateway enrichment; falls back to heuristic"),
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    project, blueprint = await service.analyze(user, project_id, use_ai=use_ai)
    return StudioAnalyzeResponse(
        project=StudioProjectResponse.model_validate(project),
        blueprint=blueprint,
    )


@router.get(
    "/projects/{project_id}/blueprint",
    response_model=StudioBlueprintResponse,
    summary="Get current blueprint",
)
def get_blueprint(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_blueprint(user, project_id)


@router.put(
    "/projects/{project_id}/blueprint",
    response_model=StudioBlueprintResponse,
    summary="Save edited blueprint as a new version",
)
def put_blueprint(
    project_id: UUID,
    payload: StudioBlueprintUpdate,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.update_blueprint(user, project_id, payload)


@router.get(
    "/projects/{project_id}/versions",
    response_model=StudioBlueprintVersionList,
    summary="List blueprint versions",
)
def list_versions(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.list_versions(user, project_id)


@router.post(
    "/projects/{project_id}/restore/{version}",
    response_model=StudioBlueprintResponse,
    summary="Restore a blueprint version (creates a new current version)",
)
def restore_version(
    project_id: UUID,
    version: int,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.restore_version(user, project_id, version)
