"""Studio service — prompts + AI Product Architect blueprints."""
from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schema import UserProfileResponse
from app.auth.tenant import can_manage_company_users
from app.studio.architect import (
    architect_blueprint,
    build_recommendations,
    validate_blueprint,
)
from app.studio.models import StudioProject, StudioProjectBlueprint, StudioProjectStatus
from app.studio.repository import StudioRepository
from app.studio.schemas import (
    BlueprintRecommendations,
    BlueprintWarning,
    ProductBlueprint,
    StudioBlueprintResponse,
    StudioBlueprintUpdate,
    StudioBlueprintVersionList,
    StudioBlueprintVersionSummary,
    StudioProjectCreate,
    StudioProjectResponse,
)


def derive_title(prompt: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit[:255]
    line = prompt.strip().splitlines()[0].strip()
    if len(line) > 80:
        return line[:77] + "..."
    return line or "Untitled product"


def _blueprint_response(row: StudioProjectBlueprint) -> StudioBlueprintResponse:
    bp = ProductBlueprint.model_validate(row.blueprint or {})
    warnings = [BlueprintWarning.model_validate(w) for w in (row.warnings or [])]
    recs = BlueprintRecommendations.model_validate(row.recommendations or {})
    return StudioBlueprintResponse(
        id=row.id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        version=row.version,
        is_current=row.is_current,
        source=row.source,
        blueprint=bp,
        warnings=warnings,
        recommendations=recs,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class StudioService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StudioRepository(db)

    def create(self, user: UserProfileResponse, payload: StudioProjectCreate) -> StudioProject:
        workspace_id = UUID(str(user.company_id))
        user_id = UUID(str(user.id)) if getattr(user, "id", None) else None
        project = StudioProject(
            workspace_id=workspace_id,
            user_id=user_id,
            title=derive_title(payload.prompt, payload.title),
            prompt=payload.prompt,
            status=StudioProjectStatus.DRAFT,
        )
        return self.repo.create(project)

    def list(
        self, user: UserProfileResponse, *, limit: int = 50, offset: int = 0
    ) -> Tuple[List[StudioProject], int]:
        return self.repo.list_for_workspace(
            UUID(str(user.company_id)), limit=limit, offset=offset
        )

    def get(self, user: UserProfileResponse, project_id: UUID) -> StudioProject:
        project = self.repo.get(project_id, UUID(str(user.company_id)))
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Studio project not found"
            )
        return project

    def delete(self, user: UserProfileResponse, project_id: UUID) -> None:
        if not can_manage_company_users(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners and admins can delete Studio projects",
            )
        project = self.get(user, project_id)
        self.repo.delete(project)

    def _persist_blueprint(
        self,
        *,
        project: StudioProject,
        user: UserProfileResponse,
        blueprint: ProductBlueprint,
        source: str,
    ) -> StudioProjectBlueprint:
        warnings = [w.model_dump() for w in validate_blueprint(blueprint)]
        recommendations = build_recommendations(blueprint).model_dump()
        self.repo.clear_current_blueprints(project.id)
        version = self.repo.next_blueprint_version(project.id)
        row = StudioProjectBlueprint(
            project_id=project.id,
            workspace_id=project.workspace_id,
            version=version,
            is_current=True,
            source=source,
            blueprint=blueprint.model_dump(),
            warnings=warnings,
            recommendations=recommendations,
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        return self.repo.create_blueprint(row)

    async def analyze(
        self, user: UserProfileResponse, project_id: UUID, *, use_ai: bool = True
    ) -> Tuple[StudioProject, StudioBlueprintResponse]:
        project = self.get(user, project_id)
        project.status = StudioProjectStatus.ANALYZING
        self.repo.save_project(project)
        try:
            blueprint, source = await architect_blueprint(
                prompt=project.prompt,
                company_id=UUID(str(user.company_id)),
                user_id=UUID(str(user.id)),
                db=self.db,
                use_ai=use_ai,
            )
            row = self._persist_blueprint(
                project=project, user=user, blueprint=blueprint, source=source
            )
            project.status = StudioProjectStatus.BLUEPRINT_READY
            self.repo.save_project(project)
            return project, _blueprint_response(row)
        except Exception as exc:
            project.status = StudioProjectStatus.FAILED
            self.repo.save_project(project)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Blueprint analysis failed: {exc}",
            ) from exc

    def get_blueprint(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioBlueprintResponse:
        project = self.get(user, project_id)
        row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No blueprint yet — run analyze first",
            )
        return _blueprint_response(row)

    def update_blueprint(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: StudioBlueprintUpdate,
    ) -> StudioBlueprintResponse:
        project = self.get(user, project_id)
        row = self._persist_blueprint(
            project=project,
            user=user,
            blueprint=payload.blueprint,
            source="manual",
        )
        if project.status in {
            StudioProjectStatus.DRAFT,
            StudioProjectStatus.ANALYZING,
            StudioProjectStatus.FAILED,
        }:
            project.status = StudioProjectStatus.BLUEPRINT_READY
            self.repo.save_project(project)
        return _blueprint_response(row)

    def list_versions(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioBlueprintVersionList:
        project = self.get(user, project_id)
        rows = self.repo.list_blueprint_versions(project.id, project.workspace_id)
        items = [
            StudioBlueprintVersionSummary(
                id=r.id,
                version=r.version,
                is_current=r.is_current,
                source=r.source,
                created_at=r.created_at,
                warning_count=len(r.warnings or []),
            )
            for r in rows
        ]
        current = next((i.version for i in items if i.is_current), None)
        return StudioBlueprintVersionList(items=items, current_version=current)

    def restore_version(
        self, user: UserProfileResponse, project_id: UUID, version: int
    ) -> StudioBlueprintResponse:
        project = self.get(user, project_id)
        old = self.repo.get_blueprint_version(project.id, project.workspace_id, version)
        if not old:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint version not found"
            )
        blueprint = ProductBlueprint.model_validate(old.blueprint or {})
        row = self._persist_blueprint(
            project=project,
            user=user,
            blueprint=blueprint,
            source="manual",
        )
        project.status = StudioProjectStatus.BLUEPRINT_READY
        self.repo.save_project(project)
        return _blueprint_response(row)

    @staticmethod
    def project_response(project: StudioProject) -> StudioProjectResponse:
        return StudioProjectResponse.model_validate(project)
