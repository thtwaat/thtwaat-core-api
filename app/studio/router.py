"""THTWAAT Studio API — /api/v2/studio (architect + module composer)."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.studio.schemas import (
    StudioAiGenerateResponse,
    StudioAiResponse,
    StudioAiUpdate,
    StudioAnalyzeResponse,
    StudioApproveRequest,
    StudioApproveResponse,
    StudioArtifactsResponse,
    StudioBackendGenerateResponse,
    StudioBackendResponse,
    StudioBackendUpdate,
    StudioBlueprintResponse,
    StudioBlueprintUpdate,
    StudioBlueprintVersionList,
    StudioBuildPlanResponse,
    StudioBuildResponse,
    StudioComposeResponse,
    StudioDeployRequest,
    StudioDeployStartResponse,
    StudioDeploymentListResponse,
    StudioDeploymentResponse,
    StudioDomainWizardRequest,
    StudioDomainWizardResponse,
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
    StudioLaunchChecklistResponse,
    StudioLaunchDiagnosticsResponse,
    StudioProjectCreate,
    StudioProjectListResponse,
    StudioProjectResponse,
    StudioRetryBuildRequest,
    StudioReviewResponse,
    StudioRollbackRequest,
    StudioRollbackResponse,
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
    use_ai: bool = Query(True, description="AI Gateway first; heuristic fallback only if AI fails"),
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


@router.post(
    "/projects/{project_id}/compose",
    response_model=StudioComposeResponse,
    summary="Compose blueprint into reusable module plan (no codegen / no deploy)",
)
def compose_project(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.compose(user, project_id)


@router.get(
    "/projects/{project_id}/build-plan",
    response_model=StudioBuildPlanResponse,
    summary="Get current module compose / build plan",
)
def get_build_plan(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_build_plan(user, project_id)


@router.post(
    "/projects/{project_id}/generate/frontend",
    response_model=StudioFrontendGenerateResponse,
    summary="Generate frontend preview manifest from build plan (no codegen / no deploy)",
)
def generate_frontend(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.generate_frontend(user, project_id)


@router.get(
    "/projects/{project_id}/frontend",
    response_model=StudioFrontendResponse,
    summary="Get current frontend preview manifest",
)
def get_frontend(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_frontend(user, project_id)


@router.put(
    "/projects/{project_id}/frontend",
    response_model=StudioFrontendResponse,
    summary="Save edited frontend manifest (edit before approval)",
)
def put_frontend(
    project_id: UUID,
    payload: StudioFrontendUpdate,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.update_frontend(user, project_id, payload)


@router.post(
    "/projects/{project_id}/generate/backend",
    response_model=StudioBackendGenerateResponse,
    summary="Generate backend architecture manifest (no codegen / no deploy)",
)
def generate_backend(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.generate_backend(user, project_id)


@router.get(
    "/projects/{project_id}/backend",
    response_model=StudioBackendResponse,
    summary="Get current backend architecture manifest",
)
def get_backend(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_backend(user, project_id)


@router.put(
    "/projects/{project_id}/backend",
    response_model=StudioBackendResponse,
    summary="Save edited backend manifest (edit before approval)",
)
def put_backend(
    project_id: UUID,
    payload: StudioBackendUpdate,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.update_backend(user, project_id, payload)


@router.post(
    "/projects/{project_id}/generate/ai",
    response_model=StudioAiGenerateResponse,
    summary="Generate AI architecture manifest (no codegen / no deploy)",
)
def generate_ai(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.generate_ai(user, project_id)


@router.get(
    "/projects/{project_id}/ai",
    response_model=StudioAiResponse,
    summary="Get current AI architecture manifest",
)
def get_ai(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_ai(user, project_id)


@router.put(
    "/projects/{project_id}/ai",
    response_model=StudioAiResponse,
    summary="Save edited AI manifest (edit before approval)",
)
def put_ai(
    project_id: UUID,
    payload: StudioAiUpdate,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.update_ai(user, project_id, payload)


@router.post(
    "/projects/{project_id}/generate/infrastructure",
    response_model=StudioInfrastructureGenerateResponse,
    summary="Generate infrastructure planning manifest (no codegen / no deploy)",
)
def generate_infrastructure(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.generate_infrastructure(user, project_id)


@router.get(
    "/projects/{project_id}/infrastructure",
    response_model=StudioInfrastructureResponse,
    summary="Get current infrastructure planning manifest",
)
def get_infrastructure(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_infrastructure(user, project_id)


@router.put(
    "/projects/{project_id}/infrastructure",
    response_model=StudioInfrastructureResponse,
    summary="Save edited infrastructure manifest (edit before approval)",
)
def put_infrastructure(
    project_id: UUID,
    payload: StudioInfrastructureUpdate,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.update_infrastructure(user, project_id, payload)


@router.get(
    "/projects/{project_id}/review",
    response_model=StudioReviewResponse,
    summary="Aggregated Review Center (no codegen / no deploy)",
)
def get_review(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_review(user, project_id)


@router.post(
    "/projects/{project_id}/approve",
    response_model=StudioApproveResponse,
    summary="Approve build plan (locks planning — does not generate source or deploy)",
)
def approve_build(
    project_id: UUID,
    payload: Optional[StudioApproveRequest] = None,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.approve_build(user, project_id, payload or StudioApproveRequest())


@router.post(
    "/projects/{project_id}/export",
    response_model=StudioExportResponse,
    summary="Export review, blueprint, or build plan (json | markdown | pdf)",
)
def export_project(
    project_id: UUID,
    payload: StudioExportRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.export_project(user, project_id, payload)


@router.post(
    "/projects/{project_id}/generate/source",
    response_model=StudioGenerateSourceResponse,
    summary="Generate source tree (requires Review Center approval)",
)
def generate_source(
    project_id: UUID,
    payload: Optional[StudioGenerateSourceRequest] = None,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.generate_source(user, project_id, payload or StudioGenerateSourceRequest())


@router.get(
    "/projects/{project_id}/build",
    response_model=StudioBuildResponse,
    summary="Get current source build status",
)
def get_build(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_build(user, project_id)


@router.get(
    "/projects/{project_id}/artifacts",
    response_model=StudioArtifactsResponse,
    summary="List generated source artifacts",
)
def get_artifacts(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_artifacts(user, project_id)


@router.get(
    "/projects/{project_id}/artifacts/download",
    summary="Download generated source ZIP",
)
def download_artifacts(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    raw, filename = service.download_artifact_bytes(user, project_id)
    return Response(
        content=raw,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/projects/{project_id}/retry",
    response_model=StudioGenerateSourceResponse,
    summary="Retry a failed/cancelled source build",
)
def retry_build(
    project_id: UUID,
    payload: Optional[StudioRetryBuildRequest] = None,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.retry_build(user, project_id, payload or StudioRetryBuildRequest())


@router.get(
    "/projects/{project_id}/build/stream",
    summary="SSE stream of build progress events",
)
def stream_build(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    import asyncio
    import json
    import time

    from app.studio.factory_events import list_build_events

    # Ensure access
    build = service.get_build(user, project_id)

    async def event_gen():
        cursor = 0
        terminal = {"completed", "failed", "cancelled"}
        # Emit current snapshot first
        yield f"event: snapshot\ndata: {json.dumps(service._build_response(service.repo.get_build(build.id)).model_dump(mode='json'), default=str)}\n\n"
        for _ in range(180):  # ~3 minutes at 1s
            events = list_build_events(build.id, after=cursor)
            if events:
                for ev in events:
                    yield f"event: {ev.get('event', 'progress')}\ndata: {json.dumps(ev, default=str)}\n\n"
                cursor += len(events)
            row = service.repo.get_build(build.id)
            if row and row.status in terminal:
                yield f"event: done\ndata: {json.dumps({'status': row.status, 'stage': row.stage}, default=str)}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post(
    "/projects/{project_id}/deploy",
    response_model=StudioDeployStartResponse,
    summary="Deploy approved source build (never regenerates source)",
)
def start_deploy(
    project_id: UUID,
    payload: Optional[StudioDeployRequest] = None,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.start_deploy(user, project_id, payload or StudioDeployRequest())


@router.get(
    "/projects/{project_id}/deployments",
    response_model=StudioDeploymentListResponse,
    summary="List deployment history",
)
def list_deployments(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.list_deployments(user, project_id)


@router.get(
    "/projects/{project_id}/deployments/{deployment_id}",
    response_model=StudioDeploymentResponse,
    summary="Get deployment detail",
)
def get_deployment(
    project_id: UUID,
    deployment_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_deployment(user, project_id, deployment_id)


@router.post(
    "/projects/{project_id}/rollback",
    response_model=StudioRollbackResponse,
    summary="Rollback to a previous completed deployment",
)
def rollback_deploy(
    project_id: UUID,
    payload: Optional[StudioRollbackRequest] = None,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.rollback_deploy(user, project_id, payload or StudioRollbackRequest())


@router.get(
    "/projects/{project_id}/launch-checklist",
    response_model=StudioLaunchChecklistResponse,
    summary="Production launch checklist (AI, billing, email, storage, domain, HTTPS, health, workers)",
)
def launch_checklist(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_launch_checklist(user, project_id)


@router.get(
    "/projects/{project_id}/launch-diagnostics",
    response_model=StudioLaunchDiagnosticsResponse,
    summary="Launch diagnostics — API, workers, Redis, DB, storage, SMTP, AI, deployment",
)
def launch_diagnostics(
    project_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.get_launch_diagnostics(user, project_id)


@router.post(
    "/projects/{project_id}/domain-wizard",
    response_model=StudioDomainWizardResponse,
    summary="Domain wizard — DNS records + verify (poll every 30s from UI)",
)
def domain_wizard(
    project_id: UUID,
    payload: StudioDomainWizardRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.domain_wizard(
        user,
        project_id,
        payload.hostname,
        auto_verify=payload.auto_verify,
    )


@router.get(
    "/projects/{project_id}/domain-wizard",
    response_model=StudioDomainWizardResponse,
    summary="Poll domain wizard status (Pending DNS → SSL Active)",
)
def domain_wizard_poll(
    project_id: UUID,
    hostname: str = Query(..., min_length=3),
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    return service.domain_wizard(user, project_id, hostname, auto_verify=True)


@router.get(
    "/projects/{project_id}/deployments/{deployment_id}/stream",
    summary="SSE stream of deployment progress",
)
def stream_deployment(
    project_id: UUID,
    deployment_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StudioService = Depends(get_studio_service),
):
    import asyncio
    import json

    from app.studio.deploy_events import list_deploy_events

    dep = service.get_deployment(user, project_id, deployment_id)

    async def event_gen():
        cursor = 0
        terminal = {"completed", "failed", "rollback"}
        yield f"event: snapshot\ndata: {json.dumps(dep.model_dump(mode='json'), default=str)}\n\n"
        for _ in range(180):
            events = list_deploy_events(deployment_id, after=cursor)
            if events:
                for ev in events:
                    yield f"event: {ev.get('event', 'progress')}\ndata: {json.dumps(ev, default=str)}\n\n"
                cursor += len(events)
            row = service.repo.get_deployment(deployment_id)
            if row and row.status in terminal:
                yield f"event: done\ndata: {json.dumps({'status': row.status, 'stage': row.stage}, default=str)}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
