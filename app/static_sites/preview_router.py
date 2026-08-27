"""THTWAAT Deploy Phase 6A — authenticated Preview Deployments API.

A dedicated router (mirrors github_router.py's own rationale) so this
surface has a self-contained diff. Same auth (get_current_user) and
company-scoping/RBAC (can_manage_company_users, via PreviewDeploymentService)
as the rest of Studio deploy. The webhook that actually CREATES/advances/
closes previews lives in github_webhook_router.py (public, signature-
authenticated) — every route here is read/manage only, for an authenticated
company owner/admin.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.database.database import get_db
from app.static_sites.preview_service import PreviewDeploymentService
from app.static_sites.schemas import PreviewDeploymentListResponse, PreviewDeploymentResponse

router = APIRouter(prefix="/api/v2/studio/static-sites", tags=["THTWAAT Deploy — Preview Deployments"])


def get_preview_service(db: Session = Depends(get_db)) -> PreviewDeploymentService:
    return PreviewDeploymentService(db)


@router.get(
    "/{site_id}/previews",
    response_model=PreviewDeploymentListResponse,
    summary="List preview deployments for a site (owners/admins only)",
)
def list_previews(
    site_id: UUID,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    user: UserProfileResponse = Depends(get_current_user),
    service: PreviewDeploymentService = Depends(get_preview_service),
):
    return service.list_previews(user, site_id, page=page, per_page=per_page)


@router.get(
    "/{site_id}/previews/{preview_id}",
    response_model=PreviewDeploymentResponse,
    summary="Get preview deployment detail (owners/admins only)",
)
def get_preview(
    site_id: UUID,
    preview_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: PreviewDeploymentService = Depends(get_preview_service),
):
    return service.get_preview(user, site_id, preview_id)


@router.get(
    "/{site_id}/previews/{preview_id}/stream",
    summary="SSE stream of preview deployment progress (owners/admins only)",
)
def stream_preview(
    site_id: UUID,
    preview_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: PreviewDeploymentService = Depends(get_preview_service),
):
    import asyncio
    import json

    from app.studio.deploy_events import list_deploy_events

    preview = service.get_preview(user, site_id, preview_id)  # auth + existence check

    async def event_gen():
        cursor = 0
        terminal = {"ready", "failed", "torn_down"}
        yield f"event: snapshot\ndata: {json.dumps(preview.model_dump(mode='json'), default=str)}\n\n"
        for _ in range(180):
            events = list_deploy_events(preview_id, after=cursor)
            if events:
                for ev in events:
                    yield f"event: {ev.get('event', 'progress')}\ndata: {json.dumps(ev, default=str)}\n\n"
                cursor += len(events)
            row = service.repo.get_preview(preview_id)
            if row and row.status in terminal:
                yield f"event: done\ndata: {json.dumps({'status': row.status, 'stage': row.stage}, default=str)}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.delete(
    "/{site_id}/previews/{preview_id}",
    response_model=PreviewDeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually close a preview deployment early (owners/admins only, async teardown)",
)
def close_preview(
    site_id: UUID,
    preview_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: PreviewDeploymentService = Depends(get_preview_service),
):
    return service.request_manual_teardown(user, site_id, preview_id)
