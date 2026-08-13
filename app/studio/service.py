"""Studio service — prompts, blueprints, and module compose / build plans."""
from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)
from app.studio.composer import compose_blueprint
from app.studio.frontend_generator import (
    generate_frontend_manifest,
    build_preview_tabs,
    build_platform_reuse_card,
    build_ai_summary_panel,
    build_preview_actions,
)
from app.studio.backend_generator import generate_backend_manifest
from app.studio.ai_generator import generate_ai_manifest
from app.studio.infrastructure_generator import generate_infrastructure_manifest
from app.studio.review import build_review_manifest, can_approve, export_review_payload
from app.studio.factory import FactoryContext, run_factory
from app.studio.factory_events import is_cancelled, publish_build_event
from app.studio.deploy import DeployContext, PROVIDERS, run_deploy
from app.studio.deploy_events import publish_deploy_event
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
    StudioProjectDeployment,
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
    StudioDeployRequest,
    StudioDeployStartResponse,
    StudioDeploymentListResponse,
    StudioDeploymentResponse,
    StudioExportRequest,
    StudioExportResponse,
    StudioFrontendApproveResponse,
    StudioFrontendCompareResponse,
    StudioFrontendGenerateResponse,
    StudioFrontendRegenerateResponse,
    StudioFrontendPreviewResponse,
    StudioFrontendResponse,
    StudioFrontendUpdate,
    StudioFrontendVersionListResponse,
    FrontendVersionDiff,
    FrontendVersionSummary,
    StudioGenerateSourceRequest,
    StudioGenerateSourceResponse,
    StudioInfrastructureGenerateResponse,
    StudioInfrastructureResponse,
    StudioInfrastructureUpdate,
    StudioProjectCreate,
    StudioProjectResponse,
    StudioRetryBuildRequest,
    StudioReviewResponse,
    StudioRollbackRequest,
    StudioRollbackResponse,
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
            # Autosave: demote previous current rows but keep them all
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

    # ── Frontend Preview UX (Production Phase 4) ──────────────────────────────

    def get_frontend_preview(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioFrontendPreviewResponse:
        """Return the enriched visual frontend preview with tabs, device previews,
        platform reuse card, AI summary panel, and action buttons."""
        project = self.get(user, project_id)
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        if not fe_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No frontend yet — run Generate Frontend first",
            )
        frontend_resp = _frontend_response(fe_row)
        manifest = FrontendManifest.model_validate(fe_row.manifest or {})

        bp_row = self.repo.get_current_blueprint(project.id, project.workspace_id)
        blueprint = (
            ProductBlueprint.model_validate(bp_row.blueprint or {}) if bp_row else None
        )

        tabs = build_preview_tabs(manifest)
        reuse_card = build_platform_reuse_card(manifest)
        ai_panel = build_ai_summary_panel(manifest, blueprint)
        actions = build_preview_actions(project_id=str(project_id))

        all_rows = self.repo.list_frontends(project.id, project.workspace_id)
        versions = [
            FrontendVersionSummary(
                id=r.id,
                version=r.version,
                is_current=bool(r.is_current),
                status=r.status or "draft",
                blueprint_version=r.blueprint_version or 0,
                build_plan_version=r.build_plan_version or 0,
                created_at=r.created_at,
            )
            for r in all_rows
        ]

        return StudioFrontendPreviewResponse(
            project=StudioProjectResponse.model_validate(project),
            frontend=frontend_resp,
            tabs=tabs,
            platform_reuse=reuse_card,
            ai_summary=ai_panel,
            actions=actions,
            versions=versions,
            interactive_preview_url=f"/api/v2/studio/projects/{project_id}/frontend/interactive",
        )

    def list_frontend_versions(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioFrontendVersionListResponse:
        """Return all saved frontend preview versions for a project."""
        project = self.get(user, project_id)
        all_rows = self.repo.list_frontends(project.id, project.workspace_id)
        items = [
            FrontendVersionSummary(
                id=r.id,
                version=r.version,
                is_current=bool(r.is_current),
                status=r.status or "draft",
                blueprint_version=r.blueprint_version or 0,
                build_plan_version=r.build_plan_version or 0,
                created_at=r.created_at,
            )
            for r in all_rows
        ]
        return StudioFrontendVersionListResponse(
            project_id=project.id,
            items=items,
            total=len(items),
        )

    def compare_frontend_versions(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        version_a: int,
        version_b: int,
    ) -> StudioFrontendCompareResponse:
        """Diff two frontend preview versions by pages."""
        project = self.get(user, project_id)
        row_a = self.repo.get_frontend_by_version(project.id, project.workspace_id, version_a)
        row_b = self.repo.get_frontend_by_version(project.id, project.workspace_id, version_b)
        if not row_a:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frontend version {version_a} not found",
            )
        if not row_b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frontend version {version_b} not found",
            )
        manifest_a = FrontendManifest.model_validate(row_a.manifest or {})
        manifest_b = FrontendManifest.model_validate(row_b.manifest or {})
        ids_a = {p.id for p in manifest_a.pages}
        ids_b = {p.id for p in manifest_b.pages}
        added = sorted(ids_b - ids_a)
        removed = sorted(ids_a - ids_b)
        page_map_a = {p.id: p for p in manifest_a.pages}
        page_map_b = {p.id: p for p in manifest_b.pages}
        changed = []
        for pid in ids_a & ids_b:
            pa, pb = page_map_a[pid], page_map_b[pid]
            if pa.kind != pb.kind or pa.route != pb.route:
                changed.append(pid)
        reuse_delta = round(
            manifest_b.summary.reuse_percent - manifest_a.summary.reuse_percent, 1
        )
        diff = FrontendVersionDiff(
            version_a=version_a,
            version_b=version_b,
            added_pages=added,
            removed_pages=removed,
            changed_pages=sorted(changed),
            reuse_delta=reuse_delta,
            page_count_delta=len(manifest_b.pages) - len(manifest_a.pages),
        )
        return StudioFrontendCompareResponse(
            project_id=project.id,
            diff=diff,
            version_a=_frontend_response(row_a),
            version_b=_frontend_response(row_b),
        )

    def approve_frontend(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioFrontendApproveResponse:
        """Approve the current frontend and auto-trigger backend generation."""
        project = self.get(user, project_id)
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        if not fe_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No frontend yet — run Generate Frontend first",
            )
        self.repo.clear_current_frontends(project.id)
        version = self.repo.next_frontend_version(project.id)
        approved_row = StudioProjectFrontend(
            project_id=project.id,
            workspace_id=project.workspace_id,
            blueprint_version=fe_row.blueprint_version,
            build_plan_version=fe_row.build_plan_version,
            version=version,
            is_current=True,
            status="approved",
            manifest=fe_row.manifest,
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_frontend(approved_row)
        frontend_resp = _frontend_response(saved)

        backend_triggered = False
        backend_error: Optional[str] = None
        try:
            self.generate_backend(user, project_id)
            backend_triggered = True
        except Exception as exc:
            backend_error = str(exc)
            logger.warning(
                "approve_frontend: auto backend generation failed for project %s: %s",
                project_id,
                exc,
            )

        return StudioFrontendApproveResponse(
            project=StudioProjectResponse.model_validate(project),
            frontend=frontend_resp,
            backend_triggered=backend_triggered,
            backend_trigger_error=backend_error,
            message=(
                "Frontend approved. Backend generation started automatically."
                if backend_triggered
                else f"Frontend approved. Backend auto-generation skipped: {backend_error}"
            ),
        )

    def regenerate_frontend(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioFrontendRegenerateResponse:
        """Regenerate the frontend manifest, autosaving all previous versions."""
        project = self.get(user, project_id)
        current = self.repo.get_current_frontend(project.id, project.workspace_id)
        prev_version: Optional[int] = current.version if current else None
        result = self.generate_frontend(user, project_id)
        return StudioFrontendRegenerateResponse(
            project=result.project,
            frontend=result.frontend,
            version=result.frontend.version,
            previous_version=prev_version,
            message=(
                f"Frontend regenerated as version {result.frontend.version}."
                + (f" Previous version {prev_version} preserved." if prev_version else "")
            ),
        )

    def download_frontend_preview(
        self, user: UserProfileResponse, project_id: UUID
    ) -> tuple:
        """Build a ZIP containing HTML previews (Desktop/Tablet/Mobile) + manifest JSON."""
        import io
        import json
        import zipfile

        project = self.get(user, project_id)
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        if not fe_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No frontend yet — run Generate Frontend first",
            )
        manifest = FrontendManifest.model_validate(fe_row.manifest or {})
        tabs = build_preview_tabs(manifest)
        reuse_card = build_platform_reuse_card(manifest)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "frontend-manifest.json",
                json.dumps(fe_row.manifest or {}, indent=2, default=str),
            )
            zf.writestr(
                "platform-reuse.json",
                json.dumps(reuse_card.model_dump(mode="json"), indent=2),
            )
            preview_tab = (
                next((t for t in tabs if t.id == "dashboard"), None) or (tabs[0] if tabs else None)
            )
            if preview_tab:
                for dp in preview_tab.device_previews:
                    zf.writestr(
                        f"preview-{dp.device}.html",
                        dp.html_snapshot.encode("utf-8"),
                    )
        return buf.getvalue(), f"frontend-preview-v{fe_row.version}.zip"

    def get_interactive_preview(
        self, user: UserProfileResponse, project_id: UUID
    ) -> str:
        """Return a self-contained live readonly HTML page merging all tab previews."""
        project = self.get(user, project_id)
        fe_row = self.repo.get_current_frontend(project.id, project.workspace_id)
        if not fe_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No frontend yet — run Generate Frontend first",
            )
        manifest = FrontendManifest.model_validate(fe_row.manifest or {})
        tabs = build_preview_tabs(manifest)
        theme_color = manifest.theme.get("primary", "#0F766E") if manifest.theme else "#0F766E"
        product_name = manifest.product_name or "Preview"

        tab_buttons = ""
        tab_panels = ""
        tab_ids = [t.id for t in tabs]
        for i, tab in enumerate(tabs):
            is_first = i == 0
            active_btn = (
                f"background:{theme_color};color:#fff;"
                if is_first
                else "background:#1e293b;color:#94a3b8;"
            )
            tab_buttons += (
                f'<button onclick="showTab(\'{tab.id}\')" id="btn-{tab.id}" '
                f'style="padding:8px 20px;border:none;border-radius:6px;cursor:pointer;'
                f'font-size:13px;font-weight:600;transition:all .2s;{active_btn}">'
                f'{tab.label}</button>'
            )
            device_panels = ""
            device_btns = ""
            for j, dp in enumerate(tab.device_previews):
                dv_display = "block" if j == 0 else "none"
                safe_html = dp.html_snapshot.replace("&", "&amp;").replace('"', "&quot;")
                device_panels += (
                    f'<div id="{tab.id}-{dp.device}" style="display:{dv_display};">'
                    f'<iframe srcdoc="{safe_html}" '
                    f'width="{dp.width_px}" height="600" '
                    f'style="border:none;border-radius:8px;max-width:100%;'
                    f'box-shadow:0 4px 32px rgba(0,0,0,.4);" '
                    f'scrolling="no"></iframe></div>'
                )
                dv_active = (
                    f"background:{theme_color};color:#fff;"
                    if j == 0
                    else "background:#1e293b;color:#64748b;"
                )
                device_btns += (
                    f'<button onclick="showDevice(\'{tab.id}\',\'{dp.device}\')" '
                    f'id="dbtn-{tab.id}-{dp.device}" '
                    f'style="padding:6px 14px;border:none;border-radius:4px;cursor:pointer;'
                    f'font-size:12px;font-weight:500;{dv_active}">'
                    f'{dp.device.capitalize()} {dp.width_px}px</button>'
                )
            tab_display = "block" if is_first else "none"
            tab_panels += (
                f'<div id="tab-{tab.id}" style="display:{tab_display};">'
                f'<div style="display:flex;gap:8px;margin-bottom:16px;">{device_btns}</div>'
                f'<div style="display:flex;justify-content:center;">{device_panels}</div>'
                f'</div>'
            )

        tab_ids_json = "[" + ",".join(f'"{t}"' for t in tab_ids) + "]"
        device_map_json = (
            "{"
            + ",".join(
                f'"{t.id}":[' + ",".join(f'"{d.device}"' for d in t.device_previews) + "]"
                for t in tabs
            )
            + "}"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{product_name} \u2014 Interactive Preview</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,system-ui,sans-serif;background:#020617;color:#f1f5f9;min-height:100vh;}}
button{{cursor:pointer;transition:all .2s;}}
</style>
</head>
<body>
<div style="max-width:1400px;margin:0 auto;padding:24px 20px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
    <div>
      <h1 style="font-size:20px;font-weight:700;">{product_name}</h1>
      <p style="font-size:13px;color:#64748b;margin-top:2px;">Interactive Frontend Preview \u2014 Readonly</p>
    </div>
    <span style="background:rgba(15,118,110,.15);border:1px solid {theme_color};
      border-radius:20px;padding:4px 14px;font-size:12px;color:{theme_color};">\u2736 THTWAAT Studio</span>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px;
    background:#0f172a;padding:8px;border-radius:10px;border:1px solid #1e293b;">
    {tab_buttons}
  </div>
  <div style="background:#0f172a;border-radius:12px;padding:24px;border:1px solid #1e293b;">
    {tab_panels}
  </div>
  <p style="text-align:center;color:#334155;font-size:11px;margin-top:16px;">
    Generated by THTWAAT Studio \u00b7 Preview only \u00b7 No source code emitted
  </p>
</div>
<script>
const tabIds={tab_ids_json};
const deviceMap={device_map_json};
const primary="{theme_color}";
function showTab(id){{
  tabIds.forEach(t=>{{
    document.getElementById("tab-"+t).style.display=t===id?"block":"none";
    const b=document.getElementById("btn-"+t);
    b.style.background=t===id?primary:"#1e293b";b.style.color=t===id?"#fff":"#94a3b8";
  }});
}}
function showDevice(tabId,device){{
  (deviceMap[tabId]||[]).forEach(d=>{{
    document.getElementById(tabId+"-"+d).style.display=d===device?"block":"none";
    const b=document.getElementById("dbtn-"+tabId+"-"+d);
    if(b){{b.style.background=d===device?primary:"#1e293b";b.style.color=d===device?"#fff":"#64748b";}}
  }});
}}
</script>
</body>
</html>"""

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

    def _deployment_response(self, row: StudioProjectDeployment) -> StudioDeploymentResponse:
        build = self.repo.get_build(row.build_id) if row.build_id else None
        builder = None
        if row.created_by:
            builder = str(row.created_by)
        commit = None
        if build and build.artifact_sha256:
            commit = build.artifact_sha256
        # Prefer values recorded on last deploy result inside health meta
        meta = row.health if isinstance(row.health, dict) else {}
        commit = meta.get("commit_sha") or commit
        builder = meta.get("builder") or builder
        from app.studio.domain_validation import allocate_free_subdomain
        from app.studio.launch import compute_launch_status, launch_status_label

        project = (
            self.db.query(StudioProject).filter(StudioProject.id == row.project_id).first()
        )
        free_host = allocate_free_subdomain(
            project_id=row.project_id,
            project_title=(project.title if project else "app"),
        )
        domain_validation = None
        if isinstance(row.health, dict) and isinstance(row.health.get("domain"), dict):
            domain_validation = row.health.get("domain")
        launch = compute_launch_status(
            live=bool(row.live),
            status=row.status or "queued",
            stage=row.stage or "queued",
            ssl=dict(row.ssl or {}),
        )
        return StudioDeploymentResponse(
            id=row.id,
            project_id=row.project_id,
            workspace_id=row.workspace_id,
            build_id=row.build_id,
            approval_id=row.approval_id,
            version=row.version,
            is_current=row.is_current,
            provider=row.provider,
            status=row.status or "queued",
            stage=row.stage or "queued",
            domain=row.domain,
            subdomain=row.subdomain,
            environment=row.environment or "production",
            live=bool(row.live),
            urls=dict(row.urls or {}),
            health=dict(row.health or {}),
            ssl=dict(row.ssl or {}),
            instructions=list(row.instructions or []),
            logs=list(row.logs or []),
            package_path=row.package_path,
            duration_ms=int(row.duration_ms or 0),
            error=row.error,
            retryable=bool(row.retryable),
            rollback_of=row.rollback_of,
            created_by=row.created_by,
            build_version=build.version if build else meta.get("build_version"),
            commit_sha=commit,
            builder=builder,
            free_subdomain=row.subdomain or free_host,
            domain_validation=domain_validation,
            launch_status=launch,
            launch_status_label=launch_status_label(launch),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _require_deploy_manager(self, user: UserProfileResponse) -> None:
        if not can_manage_company_users(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company owners and admins can deploy or rollback",
            )

    def _audit_deploy(
        self,
        *,
        company_id: UUID,
        actor_id: Optional[UUID],
        action: str,
        resource_id: str,
        metadata: Optional[dict] = None,
    ) -> None:
        try:
            from app.enterprise.models import AuditSeverity
            from app.enterprise.service import EnterpriseService

            EnterpriseService(self.db).audit(
                company_id,
                actor_id,
                action=action,
                resource_type="studio_deployment",
                resource_id=resource_id,
                severity=AuditSeverity.INFO,
                metadata=metadata or {},
                commit=True,
            )
        except Exception:  # noqa: BLE001
            logger.warning("studio_deploy_audit_failed action=%s", action)

    def _require_deployable_build(self, project: StudioProject) -> StudioProjectBuild:
        approval = self.repo.get_latest_approval(project.id, project.workspace_id)
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deploy blocked — Review Center approval required",
            )
        build = self.repo.get_current_build(project.id, project.workspace_id)
        if not build or build.status != "completed" or not build.artifact_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deploy blocked — completed source build with ZIP required (Generate Source first)",
            )
        from pathlib import Path

        if not Path(build.artifact_path).is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deploy blocked — source artifact missing on disk",
            )
        return build

    def start_deploy(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: Optional[StudioDeployRequest] = None,
    ) -> StudioDeployStartResponse:
        """Deploy an approved source build — never regenerates source."""
        self._require_deploy_manager(user)
        project = self.get(user, project_id)
        build = self._require_deployable_build(project)
        approval = self.repo.get_latest_approval(project.id, project.workspace_id)
        payload = payload or StudioDeployRequest()
        provider = (payload.provider or "vps").lower().strip()
        # normalize
        provider = provider.replace("-", "_").replace(" ", "_")
        if provider not in PROVIDERS and provider not in {"docker", "vps"}:
            # allow aliases resolved later; reject unknown early if not in list
            aliases_ok = provider in {
                "aws",
                "ecs",
                "gcp",
                "gcr",
                "k8s",
                "current_vps",
                "google_cloud",
            }
            if not aliases_ok:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported provider '{payload.provider}'",
                )

        self.repo.clear_current_deployments(project.id)
        version = self.repo.next_deployment_version(project.id)
        from app.studio.domain_validation import allocate_free_subdomain

        domain_mode = (payload.domain_mode or "free_subdomain").strip().lower().replace("-", "_")
        if domain_mode not in {"free_subdomain", "custom"}:
            domain_mode = "free_subdomain"
        free_host = allocate_free_subdomain(
            project_id=project.id, project_title=project.title or "app"
        )
        custom_domain = (payload.domain or "").strip() or None
        subdomain = (payload.subdomain or "").strip() or None
        if domain_mode == "free_subdomain":
            subdomain = free_host
            custom_domain = None
        row = StudioProjectDeployment(
            project_id=project.id,
            workspace_id=project.workspace_id,
            build_id=build.id,
            approval_id=approval.id if approval else None,
            version=version,
            is_current=True,
            provider=provider,
            status="queued",
            stage="queued",
            domain=custom_domain,
            subdomain=subdomain,
            environment=(payload.environment or "production").strip() or "production",
            live=False,
            urls={},
            health={
                "commit_sha": build.artifact_sha256,
                "builder": str(user.email) if getattr(user, "email", None) else str(user.id),
                "build_version": build.version,
                "domain_mode": domain_mode,
            },
            ssl={},
            instructions=[],
            logs=[],
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        saved = self.repo.create_deployment(row)
        publish_deploy_event(
            saved.id, "queued", {"deployment_id": str(saved.id), "provider": provider}
        )
        self._audit_deploy(
            company_id=project.workspace_id,
            actor_id=UUID(str(user.id)) if getattr(user, "id", None) else None,
            action="studio.deploy.start",
            resource_id=str(saved.id),
            metadata={
                "project_id": str(project.id),
                "provider": provider,
                "build_id": str(build.id),
                "environment": saved.environment,
            },
        )

        enqueued = False
        note = "Deployment queued"
        if payload.sync:
            self.run_deploy(saved.id)
            saved = self.repo.get_deployment(saved.id) or saved
            note = "Deployment finished synchronously"
        else:
            try:
                from app.monitoring.queue import enqueue

                enqueue(
                    {
                        "type": "studio.deploy",
                        "deployment_id": str(saved.id),
                        "project_id": str(project.id),
                        "workspace_id": str(project.workspace_id),
                        "company_id": str(project.workspace_id),
                        "user_id": str(user.id) if getattr(user, "id", None) else None,
                        "attempt": 1,
                        "timeout_seconds": 900,
                    }
                )
                enqueued = True
                note = "Enqueued on thtwaat:jobs (studio.deploy)"
            except Exception as exc:  # noqa: BLE001
                self.run_deploy(saved.id)
                saved = self.repo.get_deployment(saved.id) or saved
                note = f"Queue unavailable ({exc}); ran synchronously"

        return StudioDeployStartResponse(
            project=StudioProjectResponse.model_validate(project),
            deployment=self._deployment_response(saved),
            enqueued=enqueued,
            note=note,
        )

    def run_deploy(self, deployment_id: UUID) -> StudioProjectDeployment:
        row = self.repo.get_deployment(deployment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Deployment not found")
        project = (
            self.db.query(StudioProject).filter(StudioProject.id == row.project_id).first()
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        build = self.repo.get_build(row.build_id) if row.build_id else None
        if not build or build.status != "completed" or not build.artifact_path:
            row.status = "failed"
            row.stage = "failed"
            row.error = "Source build missing or incomplete — never regenerating"
            row.retryable = False
            return self.repo.save_deployment(row)

        from pathlib import Path

        from app.config.settings import settings

        output = (
            Path(settings.LOCAL_STORAGE_DIR)
            / "studio"
            / str(project.id)
            / "deployments"
            / str(row.id)
        )

        def on_progress(stage: str, payload: dict) -> None:
            row.stage = stage
            if stage in {
                "failed",
                "completed",
                "rollback",
                "waiting_for_domain",
                "provisioning_ssl",
            }:
                row.status = stage
            elif stage == "queued":
                row.status = "queued"
            else:
                row.status = "deploying"
            logs = list(row.logs or [])
            # Never persist secret values
            safe = {
                k: v
                for k, v in payload.items()
                if not any(
                    s in str(k).lower()
                    for s in ("secret", "password", "token", "api_key", "private")
                )
            }
            logs.append(safe)
            row.logs = logs[-300:]
            self.repo.save_deployment(row)
            publish_deploy_event(row.id, stage, safe)

        builder = None
        if row.created_by:
            builder = str(row.created_by)
        meta = row.health if isinstance(row.health, dict) else {}
        builder = meta.get("builder") or builder
        domain_mode = str(meta.get("domain_mode") or "free_subdomain")

        ctx = DeployContext(
            project_id=project.id,
            deployment_id=row.id,
            workspace_id=project.workspace_id,
            project_title=project.title or "Untitled product",
            provider=row.provider,
            build_id=build.id,
            build_version=build.version,
            artifact_path=Path(build.artifact_path),
            artifact_sha256=build.artifact_sha256,
            domain=row.domain,
            subdomain=row.subdomain,
            domain_mode=domain_mode,
            environment=row.environment or "production",
            public_api_base=getattr(settings, "PUBLIC_API_BASE_URL", "") or "",
            public_app_base=getattr(settings, "PUBLIC_APP_BASE_URL", "") or "",
            output_dir=output,
            db_session=self.db,
            actor_user_id=row.created_by,
            builder=builder,
            commit_sha=build.artifact_sha256,
            is_rollback=bool(row.rollback_of),
        )
        result = run_deploy(ctx, progress=on_progress, db_session=self.db)
        row.status = result.get("status") or row.status
        row.stage = result.get("stage") or row.stage
        row.live = bool(result.get("live"))
        row.urls = result.get("urls") or {}
        if result.get("domain") is not None:
            row.domain = result.get("domain")
        if result.get("subdomain") is not None:
            row.subdomain = result.get("subdomain")
        health = dict(result.get("health") or {})
        health["commit_sha"] = result.get("commit_sha") or build.artifact_sha256
        health["builder"] = result.get("builder") or builder
        health["build_version"] = result.get("build_version") or build.version
        health["domain_mode"] = domain_mode
        if result.get("domain_validation"):
            health["domain"] = result["domain_validation"]
        row.health = health
        row.ssl = result.get("ssl") or {}
        row.instructions = result.get("instructions") or []
        row.logs = result.get("logs") or row.logs
        row.package_path = result.get("package_path")
        row.duration_ms = int(result.get("duration_ms") or 0)
        row.error = result.get("error")
        row.retryable = bool(result.get("retryable"))
        if result.get("provider"):
            row.provider = result["provider"]
        saved = self.repo.save_deployment(row)
        self._audit_deploy(
            company_id=project.workspace_id,
            actor_id=row.created_by,
            action="studio.deploy.completed"
            if result.get("ok")
            else "studio.deploy.failed",
            resource_id=str(row.id),
            metadata={
                "status": row.status,
                "stage": row.stage,
                "live": row.live,
                "duration_ms": row.duration_ms,
                "error": row.error,
            },
        )
        return saved

    def list_deployments(
        self, user: UserProfileResponse, project_id: UUID
    ) -> StudioDeploymentListResponse:
        project = self.get(user, project_id)
        rows = self.repo.list_deployments(project.id, project.workspace_id)
        current = next((r for r in rows if r.is_current), None)
        return StudioDeploymentListResponse(
            items=[self._deployment_response(r) for r in rows],
            current_id=current.id if current else None,
            total=len(rows),
        )

    def get_deployment(
        self, user: UserProfileResponse, project_id: UUID, deployment_id: UUID
    ) -> StudioDeploymentResponse:
        project = self.get(user, project_id)
        row = self.repo.get_deployment(deployment_id)
        if not row or row.project_id != project.id or row.workspace_id != project.workspace_id:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return self._deployment_response(row)

    def get_launch_checklist(self, user: UserProfileResponse, project_id: UUID):
        from app.studio.launch import build_launch_checklist
        from app.studio.schemas import StudioLaunchChecklistResponse

        project = self.get(user, project_id)
        rows = self.repo.list_deployments(project.id, project.workspace_id)
        current = next((r for r in rows if r.is_current), None) or (rows[0] if rows else None)
        payload = build_launch_checklist(
            self.db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            deployment=current,
        )
        return StudioLaunchChecklistResponse(**payload)

    def get_launch_diagnostics(self, user: UserProfileResponse, project_id: UUID):
        from app.studio.launch import build_launch_diagnostics
        from app.studio.schemas import StudioLaunchDiagnosticsResponse

        project = self.get(user, project_id)
        rows = self.repo.list_deployments(project.id, project.workspace_id)
        current = next((r for r in rows if r.is_current), None) or (rows[0] if rows else None)
        payload = build_launch_diagnostics(
            self.db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            deployment=current,
        )
        return StudioLaunchDiagnosticsResponse(**payload)

    def domain_wizard(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        hostname: str,
        *,
        auto_verify: bool = True,
    ):
        from app.studio.launch import build_domain_wizard
        from app.studio.schemas import StudioDomainWizardResponse

        project = self.get(user, project_id)
        payload = build_domain_wizard(
            self.db,
            workspace_id=project.workspace_id,
            hostname=hostname,
            actor_id=user.id,
            auto_verify=auto_verify,
        )
        return StudioDomainWizardResponse(**payload)

    def rollback_deploy(
        self,
        user: UserProfileResponse,
        project_id: UUID,
        payload: Optional[StudioRollbackRequest] = None,
    ) -> StudioRollbackResponse:
        """One-click rollback — re-activates previous completed build on the live stack."""
        self._require_deploy_manager(user)
        project = self.get(user, project_id)
        payload = payload or StudioRollbackRequest()
        rows = self.repo.list_deployments(project.id, project.workspace_id)
        target = None
        if payload.deployment_id:
            target = self.repo.get_deployment(payload.deployment_id)
            if not target or target.project_id != project.id:
                raise HTTPException(status_code=404, detail="Rollback target not found")
        else:
            for r in rows:
                if r.is_current:
                    continue
                if r.status == "completed":
                    target = r
                    break
        if not target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No previous completed deployment to rollback to",
            )
        if not target.build_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rollback target has no build artifact",
            )
        current = self.repo.get_current_deployment(project.id, project.workspace_id)
        self.repo.clear_current_deployments(project.id)
        version = self.repo.next_deployment_version(project.id)
        row = StudioProjectDeployment(
            project_id=project.id,
            workspace_id=project.workspace_id,
            build_id=target.build_id,
            approval_id=target.approval_id,
            version=version,
            is_current=True,
            provider=target.provider,
            status="queued",
            stage="rollback",
            domain=target.domain,
            subdomain=target.subdomain,
            environment=target.environment,
            live=False,
            urls={},
            health={
                "commit_sha": (target.health or {}).get("commit_sha"),
                "builder": str(user.email) if getattr(user, "email", None) else str(user.id),
                "build_version": (target.health or {}).get("build_version"),
                "rollback_from": str(target.id),
            },
            ssl={},
            instructions=list(target.instructions or [])
            + [f"Rollback restoring deployment v{target.version}"],
            logs=[
                {
                    "event": "rollback",
                    "message": f"Restoring from deployment {target.id} (v{target.version})",
                    "from_version": target.version,
                }
            ],
            package_path=None,
            duration_ms=0,
            rollback_of=current.id if current else target.id,
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
            retryable=True,
        )
        saved = self.repo.create_deployment(row)
        publish_deploy_event(
            saved.id,
            "rollback",
            {"restored_from": str(target.id), "version": version},
        )
        self._audit_deploy(
            company_id=project.workspace_id,
            actor_id=UUID(str(user.id)) if getattr(user, "id", None) else None,
            action="studio.deploy.rollback",
            resource_id=str(saved.id),
            metadata={"restored_from": str(target.id), "from_version": target.version},
        )

        # Re-run executable deploy path against previous build artifact
        if payload.sync:
            self.run_deploy(saved.id)
            saved = self.repo.get_deployment(saved.id) or saved
        else:
            try:
                from app.monitoring.queue import enqueue

                enqueue(
                    {
                        "type": "studio.deploy",
                        "deployment_id": str(saved.id),
                        "project_id": str(project.id),
                        "workspace_id": str(project.workspace_id),
                        "company_id": str(project.workspace_id),
                        "user_id": str(user.id) if getattr(user, "id", None) else None,
                        "attempt": 1,
                        "timeout_seconds": 900,
                        "rollback": True,
                    }
                )
            except Exception:  # noqa: BLE001
                self.run_deploy(saved.id)
                saved = self.repo.get_deployment(saved.id) or saved

        return StudioRollbackResponse(
            project=StudioProjectResponse.model_validate(project),
            deployment=self._deployment_response(saved),
            restored_from=target.id,
            note=f"Rolled back to deployment v{target.version}",
        )

    @staticmethod
    def project_response(project: StudioProject) -> StudioProjectResponse:
        return StudioProjectResponse.model_validate(project)
