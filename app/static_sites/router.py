"""THTWAAT Deploy API — /api/v2/studio/static-sites.

A sibling surface to /api/v2/studio (AI-generated products) for uploaded
static HTML/ZIP websites. Same auth (get_current_user), same company
scoping and deploy/rollback RBAC gate (can_manage_company_users) as the
existing Studio deploy endpoints — see app/static_sites/service.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.config.settings import settings
from app.database.database import get_db
from app.static_sites.env_vars_service import StaticSiteEnvVarService
from app.static_sites.provider import static_site_root
from app.static_sites.schemas import (
    StaticSiteCreateRequest,
    StaticSiteDeploymentListResponse,
    StaticSiteDeploymentResponse,
    StaticSiteEnvVarCreateRequest,
    StaticSiteEnvVarListResponse,
    StaticSiteEnvVarResponse,
    StaticSiteEnvVarUpdateRequest,
    StaticSiteListResponse,
    StaticSiteResponse,
    StaticSiteRollbackRequest,
)
from app.static_sites.service import StaticSiteService

router = APIRouter(prefix="/api/v2/studio/static-sites", tags=["THTWAAT Deploy"])

ALLOWED_EXTENSIONS = {".html", ".zip"}
_UPLOAD_CHUNK = 1024 * 1024


def get_static_site_service(db: Session = Depends(get_db)) -> StaticSiteService:
    return StaticSiteService(db)


def get_env_var_service(db: Session = Depends(get_db)) -> StaticSiteEnvVarService:
    return StaticSiteEnvVarService(db)


@router.post(
    "",
    response_model=StaticSiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a static site (owners/admins only)",
)
def create_site(
    payload: StaticSiteCreateRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    return service.create_site(user, payload)


@router.get("", response_model=StaticSiteListResponse, summary="List static sites")
def list_sites(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    return service.list_sites(user, limit=limit, offset=offset)


@router.get("/{site_id}", response_model=StaticSiteResponse, summary="Get a static site")
def get_site(
    site_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    return service.get_site(user, site_id)


@router.post(
    "/{site_id}/upload",
    response_model=StaticSiteDeploymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload index.html or a .zip and deploy it (owners/admins only)",
)
async def upload_deploy(
    site_id: UUID,
    file: UploadFile = File(...),
    domain_mode: str = Form("free_subdomain"),
    domain: Optional[str] = Form(None),
    environment: str = Form("production"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only .html and .zip are supported.",
        )
    source_type = "html" if ext == ".html" else "zip"
    max_bytes = int(
        settings.STATIC_SITE_MAX_FILE_BYTES if source_type == "html" else settings.STATIC_SITE_MAX_ARCHIVE_BYTES
    )

    # Stream to a server-generated temp filename inside our own isolated
    # root — never the client-supplied filename — enforcing the size cap as
    # we go instead of buffering the whole upload in memory first.
    tmp_root = static_site_root() / "_uploads"
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_root / f"{uuid4().hex}{ext}"

    size = 0
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Upload too large ({size} bytes > {max_bytes} limit)",
                    )
                out.write(chunk)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to read upload")
    finally:
        await file.close()

    if size == 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    return service.deploy_upload(
        user,
        site_id,
        upload_path=tmp_path,
        source_type=source_type,
        original_filename=Path(filename).name or f"upload{ext}",
        upload_size_bytes=size,
        domain_mode=domain_mode,
        custom_domain=domain,
        environment=environment,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{site_id}/deployments",
    response_model=StaticSiteDeploymentListResponse,
    summary="List deployment history",
)
def list_deployments(
    site_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    return service.list_deployments(user, site_id)


@router.get(
    "/{site_id}/deployments/{deployment_id}",
    response_model=StaticSiteDeploymentResponse,
    summary="Get deployment detail",
)
def get_deployment(
    site_id: UUID,
    deployment_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    return service.get_deployment(user, site_id, deployment_id)


@router.get(
    "/{site_id}/deployments/{deployment_id}/stream",
    summary="SSE stream of deployment progress",
)
def stream_deployment(
    site_id: UUID,
    deployment_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    import asyncio
    import json

    from app.studio.deploy_events import list_deploy_events

    dep = service.get_deployment(user, site_id, deployment_id)  # auth + existence check

    async def event_gen():
        cursor = 0
        terminal = {"completed", "failed"}
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


@router.post(
    "/{site_id}/rollback",
    response_model=StaticSiteDeploymentResponse,
    summary="Rollback to a previous completed deployment (owners/admins only)",
)
def rollback(
    site_id: UUID,
    payload: Optional[StaticSiteRollbackRequest] = None,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteService = Depends(get_static_site_service),
):
    return service.rollback(user, site_id, payload or StaticSiteRollbackRequest())


# ---- THTWAAT Deploy Phase 4A — environment variables -----------------------
# Metadata-only surface (owners/admins only, matches deploy/rollback RBAC).
# No endpoint here ever returns a decrypted value — see
# app/static_sites/env_vars_service.py. Build/runtime injection is Phase 4B.


@router.get(
    "/{site_id}/env-vars",
    response_model=StaticSiteEnvVarListResponse,
    summary="List environment variables (metadata only; owners/admins only)",
)
def list_env_vars(
    site_id: UUID,
    environment: Optional[str] = Query(default=None),
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteEnvVarService = Depends(get_env_var_service),
):
    return service.list_env_vars(user, site_id, environment=environment)


@router.post(
    "/{site_id}/env-vars",
    response_model=StaticSiteEnvVarResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an environment variable (owners/admins only)",
)
def create_env_var(
    site_id: UUID,
    payload: StaticSiteEnvVarCreateRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteEnvVarService = Depends(get_env_var_service),
):
    return service.create_env_var(user, site_id, payload)


@router.get(
    "/{site_id}/env-vars/{env_id}",
    response_model=StaticSiteEnvVarResponse,
    summary="Get environment variable metadata (owners/admins only)",
)
def get_env_var(
    site_id: UUID,
    env_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteEnvVarService = Depends(get_env_var_service),
):
    return service.get_env_var(user, site_id, env_id)


@router.patch(
    "/{site_id}/env-vars/{env_id}",
    response_model=StaticSiteEnvVarResponse,
    summary="Update an environment variable's value or secrecy flag (owners/admins only)",
)
def update_env_var(
    site_id: UUID,
    env_id: UUID,
    payload: StaticSiteEnvVarUpdateRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteEnvVarService = Depends(get_env_var_service),
):
    return service.update_env_var(user, site_id, env_id, payload)


@router.delete(
    "/{site_id}/env-vars/{env_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an environment variable (owners/admins only)",
)
def delete_env_var(
    site_id: UUID,
    env_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: StaticSiteEnvVarService = Depends(get_env_var_service),
):
    service.delete_env_var(user, site_id, env_id)
    return None
