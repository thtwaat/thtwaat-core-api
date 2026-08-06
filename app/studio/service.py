"""Studio service — prompts, blueprints, and module compose / build plans."""
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
from app.studio.composer import compose_blueprint
from app.studio.frontend_generator import generate_frontend_manifest
from app.studio.backend_generator import generate_backend_manifest
from app.studio.ai_generator import generate_ai_manifest
from app.studio.infrastructure_generator import generate_infrastructure_manifest
from app.studio.review import build_review_manifest, can_approve, export_review_payload
from app.studio.factory import FactoryContext, run_factory
from app.studio.factory_events import is_cancelled, publish_build_event
from app.studio.models import (
    StudioProject,
    StudioProjectBlueprint,
    StudioProjectBuildPlan,
    StudioProjectFrontend,
    StudioProjectBackend,
    StudioProjectAi,
    StudioProjectInfrastructure,
    StudioProjectApproval,
    StudioProjectBuild,
    StudioProjectStatus,
)
from app.studio.repository import StudioRepository
from app.studio.schemas import (
    AiManifest,
    BackendManifest,
    BlueprintRecommendations,
    BlueprintWarning,
    BuildPlanStep,
    BuildPlanSummary,
    ComposedModule,
    DependencyEdge,
    FrontendManifest,
    InfraManifest,
    ProductBlueprint,
    StudioAiGenerateResponse,
    StudioAiResponse,
    StudioAiUpdate,
    StudioApproveRequest,
    StudioApproveResponse,
    StudioApprovalRecord,
    StudioArtifactsResponse,
    StudioBackendGenerateResponse,
    StudioBackendResponse,
    StudioBackendUpdate,
    StudioBlueprintResponse,
    StudioBlueprintUpdate,
    StudioBlueprintVersionList,
    StudioBlueprintVersionSummary,
    StudioBuildFileEntry,
    StudioBuildPlanResponse,
    StudioBuildResponse,
    StudioComposeResponse,
    StudioExportRequest,
    StudioExportResponse,
    StudioFrontendGenerateResponse,
    StudioFrontendResponse,
    StudioFrontendUpdate,
    StudioGenerateSourceRequest,
    StudioGenerateSourceResponse,
    StudioInfrastructureGenerateResponse,
    StudioInfrastructureResponse,
    StudioInfrastructureUpdate,
    StudioProjectCreate,
    StudioProjectResponse,
    StudioRetryBuildRequest,
    StudioReviewResponse,
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


def _build_plan_response(row: StudioProjectBuildPlan) -> StudioBuildPlanResponse:
    return StudioBuildPlanResponse(
        id=row.id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        blueprint_version=row.blueprint_version,
        version=row.version,
        is_current=row.is_current,
        modules=[ComposedModule.model_validate(m) for m in (row.modules or [])],
        dependency_graph=[DependencyEdge.model_validate(e) for e in (row.dependency_graph or [])],
        dependency_tree=list(row.dependency_tree or []),
        build_plan=[BuildPlanStep.model_validate(s) for s in (row.build_plan or [])],
        summary=BuildPlanSummary.model_validate(row.summary or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _frontend_response(row: StudioProjectFrontend) -> StudioFrontendResponse:
    return StudioFrontendResponse(
        id=row.id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        blueprint_version=row.blueprint_version,
        build_plan_version=row.build_plan_version,
        version=row.version,
        is_current=row.is_current,
        status=row.status or "draft",
        manifest=FrontendManifest.model_validate(row.manifest or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _backend_response(row: StudioProjectBackend) -> StudioBackendResponse:
    return StudioBackendResponse(
        id=row.id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        blueprint_version=row.blueprint_version,
        build_plan_version=row.build_plan_version,
        frontend_version=row.frontend_version,
        version=row.version,
        is_current=row.is_current,
        status=row.status or "draft",
        manifest=BackendManifest.model_validate(row.manifest or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _ai_response(row: StudioProjectAi) -> StudioAiResponse:
    return StudioAiResponse(
        id=row.id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        blueprint_version=row.blueprint_version,
        build_plan_version=row.build_plan_version,
        frontend_version=row.frontend_version,
        backend_version=row.backend_version,
        version=row.version,
        is_current=row.is_current,
        status=row.status or "draft",
        manifest=AiManifest.model_validate(row.manifest or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _infrastructure_response(row: StudioProjectInfrastructure) -> StudioInfrastructureResponse:
    return StudioInfrastructureResponse(
        id=row.id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        blueprint_version=row.blueprint_version,
        build_plan_version=row.build_plan_version,
        frontend_version=row.frontend_version,
        backend_version=row.backend_version,
        ai_version=row.ai_version,
        version=row.version,
        is_current=row.is_current,
        status=row.status or "draft",
        manifest=InfraManifest.model_validate(row.manifest or {}),
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

    def compose(self, user: UserProfileResponse, project_id: UUID) -> StudioComposeResponse:
        """Map approved blueprint → module plan (reuse existing platform modules)."""
        project = self.get(user, project_id)
        bp_row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        if not bp_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No blueprint to compose — run Generate Blueprint first",
            )
        blueprint = ProductBlueprint.model_validate(bp_row.blueprint or {})
        result = compose_blueprint(
            blueprint,
            recommendations=bp_row.recommendations or {},
        )
        self.repo.clear_current_build_plans(project.id)
        version = self.repo.next_build_plan_version(project.id)
        row = StudioProjectBuildPlan(
            project_id=project.id,
            workspace_id=project.workspace_id,
            blueprint_version=bp_row.version,
            version=version,
            is_current=True,
            modules=[m.model_dump(mode="json") for m in result.modules],
            dependency_graph=[e.model_dump(mode="json") for e in result.dependency_graph],
            dependency_tree=result.dependency_tree,
            build_plan=[s.model_dump(mode="json") for s in result.build_plan],
            summary=result.summary.model_dump(mode="json"),
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_build_plan(row)
        project.status = StudioProjectStatus.APPROVED
        self.repo.save_project(project)
        return StudioComposeResponse(
            project=StudioProjectResponse.model_validate(project),
            build_plan=_build_plan_response(saved),
        )

    def get_build_plan(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioBuildPlanResponse:
        project = self.get(user, project_id)
        row = self.repo.get_current_build_plan(project.id, project.workspace_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No build plan yet — run Compose Modules first",
            )
        return _build_plan_response(row)

    def generate_frontend(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioFrontendGenerateResponse:
        """Generate frontend preview manifest from build plan (no codegen / no deploy)."""
        project = self.get(user, project_id)
        bp_row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        if not bp_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No blueprint — run Generate Blueprint first",
            )
        plan_row = self.repo.get_current_build_plan(project.id, project.workspace_id)
        if not plan_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No build plan — run Compose Modules first",
            )
        blueprint = ProductBlueprint.model_validate(bp_row.blueprint or {})
        modules = [ComposedModule.model_validate(m) for m in (plan_row.modules or [])]
        project.status = StudioProjectStatus.BUILDING
        self.repo.save_project(project)
        try:
            manifest = generate_frontend_manifest(
                blueprint=blueprint,
                modules=modules,
                project_title=project.title,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
            )
            self.repo.clear_current_frontends(project.id)
            version = self.repo.next_frontend_version(project.id)
            row = StudioProjectFrontend(
                project_id=project.id,
                workspace_id=project.workspace_id,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
                version=version,
                is_current=True,
                status="draft",
                manifest=manifest.model_dump(mode="json"),
                created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
            )
            saved = self.repo.create_frontend(row)
            # Stay approved — Phase 4 is preview only (no deploy / no backend)
            project.status = StudioProjectStatus.APPROVED
            self.repo.save_project(project)
            return StudioFrontendGenerateResponse(
                project=StudioProjectResponse.model_validate(project),
                frontend=_frontend_response(saved),
            )
        except Exception as exc:
            project.status = StudioProjectStatus.FAILED
            self.repo.save_project(project)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Frontend generation failed: {exc}",
            ) from exc

    def get_frontend(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioFrontendResponse:
        project = self.get(user, project_id)
        row = self.repo.get_current_frontend(project.id, project.workspace_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No frontend yet — run Generate Frontend first",
            )
        return _frontend_response(row)

    def update_frontend(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: StudioFrontendUpdate,
    ) -> StudioFrontendResponse:
        """Save edited frontend manifest as a new version (edit before approval)."""
        project = self.get(user, project_id)
        current = self.repo.get_current_frontend(project.id, project.workspace_id)
        if not current:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No frontend yet — run Generate Frontend first",
            )
        status_value = (payload.status or current.status or "draft").strip().lower()
        if status_value not in {"draft", "approved"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Frontend status must be draft or approved",
            )
        self.repo.clear_current_frontends(project.id)
        version = self.repo.next_frontend_version(project.id)
        row = StudioProjectFrontend(
            project_id=project.id,
            workspace_id=project.workspace_id,
            blueprint_version=current.blueprint_version,
            build_plan_version=current.build_plan_version,
            version=version,
            is_current=True,
            status=status_value,
            manifest=payload.manifest.model_dump(mode="json"),
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_frontend(row)
        return _frontend_response(saved)

    def generate_backend(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioBackendGenerateResponse:
        """Generate backend architecture manifest (no codegen / no deploy)."""
        project = self.get(user, project_id)
        bp_row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        if not bp_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No blueprint — run Generate Blueprint first",
            )
        plan_row = self.repo.get_current_build_plan(project.id, project.workspace_id)
        if not plan_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No build plan — run Compose Modules first",
            )
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        if not fe_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No frontend — run Generate Frontend first",
            )
        blueprint = ProductBlueprint.model_validate(bp_row.blueprint or {})
        modules = [ComposedModule.model_validate(m) for m in (plan_row.modules or [])]
        frontend = FrontendManifest.model_validate(fe_row.manifest or {})
        project.status = StudioProjectStatus.BUILDING
        self.repo.save_project(project)
        try:
            manifest = generate_backend_manifest(
                blueprint=blueprint,
                modules=modules,
                frontend=frontend,
                project_title=project.title,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
                frontend_version=fe_row.version,
            )
            self.repo.clear_current_backends(project.id)
            version = self.repo.next_backend_version(project.id)
            row = StudioProjectBackend(
                project_id=project.id,
                workspace_id=project.workspace_id,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
                frontend_version=fe_row.version,
                version=version,
                is_current=True,
                status="draft",
                manifest=manifest.model_dump(mode="json"),
                created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
            )
            saved = self.repo.create_backend(row)
            project.status = StudioProjectStatus.APPROVED
            self.repo.save_project(project)
            return StudioBackendGenerateResponse(
                project=StudioProjectResponse.model_validate(project),
                backend=_backend_response(saved),
            )
        except Exception as exc:
            project.status = StudioProjectStatus.FAILED
            self.repo.save_project(project)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Backend generation failed: {exc}",
            ) from exc

    def get_backend(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioBackendResponse:
        project = self.get(user, project_id)
        row = self.repo.get_current_backend(project.id, project.workspace_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No backend yet — run Generate Backend first",
            )
        return _backend_response(row)

    def update_backend(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: StudioBackendUpdate,
    ) -> StudioBackendResponse:
        project = self.get(user, project_id)
        current = self.repo.get_current_backend(project.id, project.workspace_id)
        if not current:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No backend yet — run Generate Backend first",
            )
        status_value = (payload.status or current.status or "draft").strip().lower()
        if status_value not in {"draft", "approved"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backend status must be draft or approved",
            )
        self.repo.clear_current_backends(project.id)
        version = self.repo.next_backend_version(project.id)
        row = StudioProjectBackend(
            project_id=project.id,
            workspace_id=project.workspace_id,
            blueprint_version=current.blueprint_version,
            build_plan_version=current.build_plan_version,
            frontend_version=current.frontend_version,
            version=version,
            is_current=True,
            status=status_value,
            manifest=payload.manifest.model_dump(mode="json"),
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_backend(row)
        return _backend_response(saved)

    def generate_ai(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioAiGenerateResponse:
        """Generate AI architecture manifest (no codegen / no deploy)."""
        project = self.get(user, project_id)
        bp_row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        if not bp_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No blueprint — run Generate Blueprint first",
            )
        plan_row = self.repo.get_current_build_plan(project.id, project.workspace_id)
        if not plan_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No build plan — run Compose Modules first",
            )
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        be_row = self.repo.get_current_backend(project.id, project.workspace_id)
        if not be_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No backend — run Generate Backend first",
            )
        blueprint = ProductBlueprint.model_validate(bp_row.blueprint or {})
        modules = [ComposedModule.model_validate(m) for m in (plan_row.modules or [])]
        backend = BackendManifest.model_validate(be_row.manifest or {})
        project.status = StudioProjectStatus.BUILDING
        self.repo.save_project(project)
        try:
            manifest = generate_ai_manifest(
                blueprint=blueprint,
                modules=modules,
                backend=backend,
                project_title=project.title,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
                frontend_version=fe_row.version if fe_row else 0,
                backend_version=be_row.version,
            )
            self.repo.clear_current_ai(project.id)
            version = self.repo.next_ai_version(project.id)
            row = StudioProjectAi(
                project_id=project.id,
                workspace_id=project.workspace_id,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
                frontend_version=fe_row.version if fe_row else 0,
                backend_version=be_row.version,
                version=version,
                is_current=True,
                status="draft",
                manifest=manifest.model_dump(mode="json"),
                created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
            )
            saved = self.repo.create_ai(row)
            project.status = StudioProjectStatus.APPROVED
            self.repo.save_project(project)
            return StudioAiGenerateResponse(
                project=StudioProjectResponse.model_validate(project),
                ai=_ai_response(saved),
            )
        except Exception as exc:
            project.status = StudioProjectStatus.FAILED
            self.repo.save_project(project)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI generation failed: {exc}",
            ) from exc

    def get_ai(self, user: UserProfileResponse, project_id: UUID) -> StudioAiResponse:
        project = self.get(user, project_id)
        row = self.repo.get_current_ai(project.id, project.workspace_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No AI manifest yet — run Generate AI first",
            )
        return _ai_response(row)

    def update_ai(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: StudioAiUpdate,
    ) -> StudioAiResponse:
        project = self.get(user, project_id)
        current = self.repo.get_current_ai(project.id, project.workspace_id)
        if not current:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No AI manifest yet — run Generate AI first",
            )
        status_value = (payload.status or current.status or "draft").strip().lower()
        if status_value not in {"draft", "approved"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI status must be draft or approved",
            )
        self.repo.clear_current_ai(project.id)
        version = self.repo.next_ai_version(project.id)
        row = StudioProjectAi(
            project_id=project.id,
            workspace_id=project.workspace_id,
            blueprint_version=current.blueprint_version,
            build_plan_version=current.build_plan_version,
            frontend_version=current.frontend_version,
            backend_version=current.backend_version,
            version=version,
            is_current=True,
            status=status_value,
            manifest=payload.manifest.model_dump(mode="json"),
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_ai(row)
        return _ai_response(saved)

    def generate_infrastructure(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioInfrastructureGenerateResponse:
        """Generate infrastructure planning manifest (no codegen / no deploy)."""
        project = self.get(user, project_id)
        bp_row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        if not bp_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No blueprint — run Generate Blueprint first",
            )
        plan_row = self.repo.get_current_build_plan(project.id, project.workspace_id)
        if not plan_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No build plan — run Compose Modules first",
            )
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        be_row = self.repo.get_current_backend(project.id, project.workspace_id)
        if not be_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No backend — run Generate Backend first",
            )
        ai_row = self.repo.get_current_ai(project.id, project.workspace_id)
        if not ai_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No AI manifest — run Generate AI first",
            )
        blueprint = ProductBlueprint.model_validate(bp_row.blueprint or {})
        modules = [ComposedModule.model_validate(m) for m in (plan_row.modules or [])]
        backend = BackendManifest.model_validate(be_row.manifest or {})
        ai = AiManifest.model_validate(ai_row.manifest or {})
        project.status = StudioProjectStatus.BUILDING
        self.repo.save_project(project)
        try:
            manifest = generate_infrastructure_manifest(
                blueprint=blueprint,
                modules=modules,
                backend=backend,
                ai=ai,
                project_title=project.title,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
                frontend_version=fe_row.version if fe_row else 0,
                backend_version=be_row.version,
                ai_version=ai_row.version,
            )
            self.repo.clear_current_infrastructure(project.id)
            version = self.repo.next_infrastructure_version(project.id)
            row = StudioProjectInfrastructure(
                project_id=project.id,
                workspace_id=project.workspace_id,
                blueprint_version=bp_row.version,
                build_plan_version=plan_row.version,
                frontend_version=fe_row.version if fe_row else 0,
                backend_version=be_row.version,
                ai_version=ai_row.version,
                version=version,
                is_current=True,
                status="draft",
                manifest=manifest.model_dump(mode="json"),
                created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
            )
            saved = self.repo.create_infrastructure(row)
            project.status = StudioProjectStatus.APPROVED
            self.repo.save_project(project)
            return StudioInfrastructureGenerateResponse(
                project=StudioProjectResponse.model_validate(project),
                infrastructure=_infrastructure_response(saved),
            )
        except Exception as exc:
            project.status = StudioProjectStatus.FAILED
            self.repo.save_project(project)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Infrastructure generation failed: {exc}",
            ) from exc

    def get_infrastructure(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioInfrastructureResponse:
        project = self.get(user, project_id)
        row = self.repo.get_current_infrastructure(project.id, project.workspace_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No infrastructure yet — run Generate Infrastructure first",
            )
        return _infrastructure_response(row)

    def update_infrastructure(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: StudioInfrastructureUpdate,
    ) -> StudioInfrastructureResponse:
        project = self.get(user, project_id)
        current = self.repo.get_current_infrastructure(project.id, project.workspace_id)
        if not current:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No infrastructure yet — run Generate Infrastructure first",
            )
        status_value = (payload.status or current.status or "draft").strip().lower()
        if status_value not in {"draft", "approved"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Infrastructure status must be draft or approved",
            )
        self.repo.clear_current_infrastructure(project.id)
        version = self.repo.next_infrastructure_version(project.id)
        row = StudioProjectInfrastructure(
            project_id=project.id,
            workspace_id=project.workspace_id,
            blueprint_version=current.blueprint_version,
            build_plan_version=current.build_plan_version,
            frontend_version=current.frontend_version,
            backend_version=current.backend_version,
            ai_version=current.ai_version,
            version=version,
            is_current=True,
            status=status_value,
            manifest=payload.manifest.model_dump(mode="json"),
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_infrastructure(row)
        return _infrastructure_response(saved)

    def _load_review_context(self, project: StudioProject):
        bp_row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        plan_row = self.repo.get_current_build_plan(project.id, project.workspace_id)
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        be_row = self.repo.get_current_backend(project.id, project.workspace_id)
        ai_row = self.repo.get_current_ai(project.id, project.workspace_id)
        infra_row = self.repo.get_current_infrastructure(project.id, project.workspace_id)
        return bp_row, plan_row, fe_row, be_row, ai_row, infra_row

    def _build_review_for_project(self, project: StudioProject):
        bp_row, plan_row, fe_row, be_row, ai_row, infra_row = self._load_review_context(
            project
        )
        if not bp_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No blueprint — run Generate Blueprint first",
            )
        blueprint = ProductBlueprint.model_validate(bp_row.blueprint or {})
        modules: List[ComposedModule] = []
        dependency_graph: List[DependencyEdge] = []
        build_plan_version = None
        if plan_row:
            modules = [ComposedModule.model_validate(m) for m in (plan_row.modules or [])]
            dependency_graph = [
                DependencyEdge.model_validate(e) for e in (plan_row.dependency_graph or [])
            ]
            build_plan_version = plan_row.version
        frontend = (
            FrontendManifest.model_validate(fe_row.manifest or {}) if fe_row else None
        )
        backend = (
            BackendManifest.model_validate(be_row.manifest or {}) if be_row else None
        )
        ai = AiManifest.model_validate(ai_row.manifest or {}) if ai_row else None
        infra = (
            InfraManifest.model_validate(infra_row.manifest or {}) if infra_row else None
        )
        status_value = (
            project.status.value
            if hasattr(project.status, "value")
            else str(project.status)
        )
        review = build_review_manifest(
            project_title=project.title or "Untitled product",
            project_status=status_value,
            blueprint=blueprint,
            modules=modules,
            dependency_graph=dependency_graph,
            frontend=frontend,
            backend=backend,
            ai=ai,
            infra=infra,
            blueprint_version=bp_row.version,
            build_plan_version=build_plan_version,
            frontend_version=fe_row.version if fe_row else None,
            frontend_status=fe_row.status if fe_row else None,
            backend_version=be_row.version if be_row else None,
            backend_status=be_row.status if be_row else None,
            ai_version=ai_row.version if ai_row else None,
            ai_status=ai_row.status if ai_row else None,
            infra_version=infra_row.version if infra_row else None,
            infra_status=infra_row.status if infra_row else None,
        )
        return review, bp_row, plan_row, fe_row, be_row, ai_row, infra_row

    def get_review(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioReviewResponse:
        """Aggregate all Studio manifests into a review (no codegen / no deploy)."""
        project = self.get(user, project_id)
        review, *_ = self._build_review_for_project(project)
        return StudioReviewResponse(
            project=StudioProjectResponse.model_validate(project),
            review=review,
        )

    def approve_build(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: Optional[StudioApproveRequest] = None,
    ) -> StudioApproveResponse:
        """Final build approval — locks planning; does not generate source or deploy."""
        project = self.get(user, project_id)
        review, bp_row, plan_row, fe_row, be_row, ai_row, infra_row = (
            self._build_review_for_project(project)
        )
        ok, reason = can_approve(review)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve build — {reason}",
            )
        notes = (payload.notes if payload else None) or None
        row = StudioProjectApproval(
            project_id=project.id,
            workspace_id=project.workspace_id,
            blueprint_version=bp_row.version if bp_row else 0,
            build_plan_version=plan_row.version if plan_row else 0,
            frontend_version=fe_row.version if fe_row else 0,
            backend_version=be_row.version if be_row else 0,
            ai_version=ai_row.version if ai_row else 0,
            infrastructure_version=infra_row.version if infra_row else 0,
            notes=notes,
            snapshot=review.model_dump(mode="json"),
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_approval(row)
        project.status = StudioProjectStatus.COMPLETED
        self.repo.save_project(project)
        return StudioApproveResponse(
            project=StudioProjectResponse.model_validate(project),
            approval=StudioApprovalRecord.model_validate(saved),
            review=review,
        )

    def export_project(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: StudioExportRequest,
    ) -> StudioExportResponse:
        """Export review / blueprint / build plan as JSON, Markdown, or PDF."""
        project = self.get(user, project_id)
        review, bp_row, plan_row, *_rest = self._build_review_for_project(project)
        blueprint = (
            ProductBlueprint.model_validate(bp_row.blueprint or {}) if bp_row else None
        )
        build_plan = None
        if plan_row:
            build_plan = {
                "version": plan_row.version,
                "blueprint_version": plan_row.blueprint_version,
                "modules": plan_row.modules or [],
                "dependency_graph": plan_row.dependency_graph or [],
                "dependency_tree": plan_row.dependency_tree or [],
                "build_plan": plan_row.build_plan or [],
                "summary": plan_row.summary or {},
            }
        try:
            exported = export_review_payload(
                review=review,
                kind=payload.kind,
                format=payload.format,
                blueprint=blueprint,
                build_plan=build_plan,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return StudioExportResponse(**exported)

    def _build_response(self, row: StudioProjectBuild) -> StudioBuildResponse:
        files = [
            StudioBuildFileEntry.model_validate(f) if isinstance(f, dict) else f
            for f in (row.file_manifest or [])
        ]
        return StudioBuildResponse(
            id=row.id,
            project_id=row.project_id,
            workspace_id=row.workspace_id,
            approval_id=row.approval_id,
            version=row.version,
            is_current=row.is_current,
            status=row.status or "queued",
            stage=row.stage or "queued",
            agent_statuses=dict(row.agent_statuses or {}),
            logs=list(row.logs or []),
            file_manifest=files,
            artifact_path=row.artifact_path,
            artifact_sha256=row.artifact_sha256,
            file_count=int(row.file_count or 0),
            error=row.error,
            retryable=bool(row.retryable),
            retry_of=row.retry_of,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _artifact_root(self, project_id: UUID, build_id: UUID) -> "Path":
        from pathlib import Path

        from app.config.settings import settings

        base = Path(settings.LOCAL_STORAGE_DIR) / "studio" / str(project_id) / "builds" / str(build_id)
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _require_approval(self, project: StudioProject) -> StudioProjectApproval:
        approval = self.repo.get_latest_approval(project.id, project.workspace_id)
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Build not approved — run Review Center Approve Build first",
            )
        status_value = (
            project.status.value
            if hasattr(project.status, "value")
            else str(project.status)
        )
        if status_value not in {"completed", "building", "failed"}:
            # Must have been approved at least once (COMPLETED). Allow retry after failed builds.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project must be approved (completed) before source generation",
            )
        return approval

    def _factory_context(
        self, project: StudioProject, approval: StudioProjectApproval
    ) -> FactoryContext:
        bp_row, plan_row, fe_row, be_row, ai_row, infra_row = self._load_review_context(
            project
        )
        if not bp_row or not plan_row or not fe_row or not be_row or not ai_row or not infra_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All manifests required (blueprint, plan, frontend, backend, AI, infra)",
            )
        return FactoryContext(
            project_id=project.id,
            project_title=project.title or "Untitled product",
            blueprint=ProductBlueprint.model_validate(bp_row.blueprint or {}),
            modules=[ComposedModule.model_validate(m) for m in (plan_row.modules or [])],
            frontend=FrontendManifest.model_validate(fe_row.manifest or {}),
            backend=BackendManifest.model_validate(be_row.manifest or {}),
            ai=AiManifest.model_validate(ai_row.manifest or {}),
            infra=InfraManifest.model_validate(infra_row.manifest or {}),
            approval_id=approval.id,
            versions={
                "blueprint": bp_row.version,
                "build_plan": plan_row.version,
                "frontend": fe_row.version,
                "backend": be_row.version,
                "ai": ai_row.version,
                "infrastructure": infra_row.version,
            },
        )

    def generate_source(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: Optional[StudioGenerateSourceRequest] = None,
    ) -> StudioGenerateSourceResponse:
        """Start AI Software Factory source generation — requires prior approval."""
        project = self.get(user, project_id)
        approval = self._require_approval(project)
        payload = payload or StudioGenerateSourceRequest()

        self.repo.clear_current_builds(project.id)
        version = self.repo.next_build_version(project.id)
        row = StudioProjectBuild(
            project_id=project.id,
            workspace_id=project.workspace_id,
            approval_id=approval.id,
            version=version,
            is_current=True,
            status="queued",
            stage="queued",
            agent_statuses={a: {"status": "queued", "message": ""} for a in (
                "planner",
                "frontend",
                "backend",
                "database",
                "ai",
                "infrastructure",
                "security",
                "qa",
                "documentation",
            )},
            logs=[],
            file_manifest=[],
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_build(row)
        project.status = StudioProjectStatus.BUILDING
        self.repo.save_project(project)
        publish_build_event(saved.id, "queued", {"build_id": str(saved.id), "version": version})

        enqueued = False
        note = "Source generation queued"
        if payload.sync:
            self.run_build(saved.id)
            saved = self.repo.get_build(saved.id) or saved
            note = "Source generation completed synchronously"
        else:
            try:
                from app.monitoring.queue import enqueue

                enqueue(
                    {
                        "type": "studio.build",
                        "build_id": str(saved.id),
                        "project_id": str(project.id),
                        "workspace_id": str(project.workspace_id),
                        "company_id": str(project.workspace_id),
                        "user_id": str(user.id) if getattr(user, "id", None) else None,
                    }
                )
                enqueued = True
                note = "Enqueued on thtwaat:jobs (studio.build)"
            except Exception as exc:  # noqa: BLE001
                # Fallback for local/dev without Redis
                self.run_build(saved.id)
                saved = self.repo.get_build(saved.id) or saved
                note = f"Queue unavailable ({exc}); ran synchronously"

        return StudioGenerateSourceResponse(
            project=StudioProjectResponse.model_validate(project),
            build=self._build_response(saved),
            enqueued=enqueued,
            note=note,
        )

    def run_build(self, build_id: UUID) -> StudioProjectBuild:
        """Execute factory for a queued build (worker or sync)."""
        row = self.repo.get_build(build_id)
        if not row:
            raise HTTPException(status_code=404, detail="Build not found")
        project = (
            self.db.query(StudioProject).filter(StudioProject.id == row.project_id).first()
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        approval = self.repo.get_latest_approval(project.id, project.workspace_id)
        if not approval:
            row.status = "failed"
            row.stage = "failed"
            row.error = "Missing approval — cannot generate source"
            row.retryable = False
            return self.repo.save_build(row)

        try:
            ctx = self._factory_context(project, approval)
        except HTTPException as exc:
            row.status = "failed"
            row.stage = "failed"
            row.error = str(exc.detail)
            row.retryable = True
            project.status = StudioProjectStatus.FAILED
            self.repo.save_project(project)
            return self.repo.save_build(row)

        output_dir = self._artifact_root(project.id, row.id)

        def on_progress(event: str, payload: dict) -> None:
            row.stage = event
            if event in {"planning", "generating", "validating", "packaging"} or event.startswith(
                "generating_"
            ):
                row.status = "generating" if event.startswith("generating") else event
                if event == "planning":
                    row.status = "planning"
                if event == "validating":
                    row.status = "validating"
            if event == "completed":
                row.status = "completed"
            if event == "failed":
                row.status = "failed"
            if event == "cancelled":
                row.status = "cancelled"
            agent = payload.get("agent")
            if agent:
                statuses = dict(row.agent_statuses or {})
                statuses[agent] = {
                    "status": "running" if event.startswith("generating") or event == "planning" else statuses.get(agent, {}).get("status", "running"),
                    "message": payload.get("message") or "",
                }
                row.agent_statuses = statuses
            logs = list(row.logs or [])
            logs.append(payload)
            row.logs = logs[-200:]
            self.repo.save_build(row)
            publish_build_event(row.id, event, payload)

        result = run_factory(
            ctx,
            output_dir=output_dir,
            progress=on_progress,
            cancel_check=lambda: is_cancelled(row.id),
        )
        row.agent_statuses = result.get("agent_statuses") or row.agent_statuses
        row.logs = result.get("logs") or row.logs
        row.file_manifest = result.get("files") or []
        row.file_count = int(result.get("file_count") or len(row.file_manifest or []))
        row.artifact_path = result.get("artifact_path")
        row.artifact_sha256 = result.get("artifact_sha256")
        row.error = result.get("error")
        row.retryable = bool(result.get("retryable"))
        row.status = result.get("status") or row.status
        row.stage = result.get("stage") or row.stage
        saved = self.repo.save_build(row)
        if result.get("ok"):
            project.status = StudioProjectStatus.COMPLETED
        elif result.get("status") == "cancelled":
            project.status = StudioProjectStatus.COMPLETED  # stay approved
        else:
            project.status = StudioProjectStatus.FAILED
        self.repo.save_project(project)
        return saved

    def get_build(self, user: UserProfileResponse, project_id: UUID) -> StudioBuildResponse:
        project = self.get(user, project_id)
        row = self.repo.get_current_build(project.id, project.workspace_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No build yet — run Generate Source after approval",
            )
        return self._build_response(row)

    def get_artifacts(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioArtifactsResponse:
        build = self.get_build(user, project_id)
        roots = sorted(
            {
                f.path.split("/", 1)[0]
                for f in build.file_manifest
                if f.path and "/" in f.path
            }
            | ({"README.md"} if any(f.path == "README.md" for f in build.file_manifest) else set())
        )
        return StudioArtifactsResponse(
            build_id=build.id,
            version=build.version,
            status=build.status,
            file_count=build.file_count,
            artifact_sha256=build.artifact_sha256,
            download_available=bool(build.artifact_path) and build.status == "completed",
            files=build.file_manifest,
            tree_roots=list(roots),
        )

    def download_artifact_bytes(
        self, user: UserProfileResponse, project_id: UUID
    ) -> tuple[bytes, str]:
        project = self.get(user, project_id)
        row = self.repo.get_current_build(project.id, project.workspace_id)
        if not row or not row.artifact_path or row.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ZIP artifact not available",
            )
        from pathlib import Path

        path = Path(row.artifact_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Artifact file missing on disk")
        return path.read_bytes(), f"{project.title or 'studio'}-v{row.version}-source.zip"

    def retry_build(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: Optional[StudioRetryBuildRequest] = None,
    ) -> StudioGenerateSourceResponse:
        project = self.get(user, project_id)
        current = self.repo.get_current_build(project.id, project.workspace_id)
        if current and current.status not in {"failed", "cancelled", "retryable"}:
            if not current.retryable and current.status != "failed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Current build status '{current.status}' is not retryable",
                )
        payload = payload or StudioRetryBuildRequest()
        # Create a new version linked to prior
        result = self.generate_source(
            user,
            project_id,
            StudioGenerateSourceRequest(sync=payload.sync, notes=payload.notes),
        )
        if current and result.build:
            # stamp retry_of on the new build
            row = self.repo.get_build(result.build.id)
            if row:
                row.retry_of = current.id
                self.repo.save_build(row)
                result = StudioGenerateSourceResponse(
                    project=result.project,
                    build=self._build_response(row),
                    enqueued=result.enqueued,
                    note=result.note,
                )
        return result

    @staticmethod
    def project_response(project: StudioProject) -> StudioProjectResponse:
        return StudioProjectResponse.model_validate(project)
