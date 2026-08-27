"""THTWAAT Deploy Phase 5 — GitHub Connect API.

A dedicated router (rather than adding routes to static_sites/router.py)
so this new, security-sensitive surface has a self-contained diff and
cannot accidentally disturb the existing, working manual ZIP/HTML upload
endpoints. Same auth (get_current_user) and company-scoping/RBAC
(can_manage_company_users, via GitHubService) as the rest of Studio deploy
— see app/static_sites/github_service.py.

/github/callback is the one deliberate exception: it has no
get_current_user dependency because GitHub itself redirects the browser
here directly (no bearer token available). It is a single, site_id-less
endpoint because a GitHub App's "Setup URL" is configured once, globally,
in the App's github.com settings and cannot be templated per site — the
site/workspace/user this callback is for comes entirely from the
single-use state row it consumes (see GitHubService.handle_callback).
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.config.settings import settings
from app.database.database import get_db
from app.static_sites.github_service import GitHubService
from app.static_sites.schemas import (
    GitHubBranchListResponse,
    GitHubConnectionResponse,
    GitHubConnectStartResponse,
    GitHubRepositoryListResponse,
    GitHubSelectRepositoryRequest,
)

router = APIRouter(prefix="/api/v2/studio/static-sites", tags=["THTWAAT Deploy — GitHub"])


def get_github_service(db: Session = Depends(get_db)) -> GitHubService:
    return GitHubService(db)


def _frontend_redirect(*, site_id: Optional[UUID] = None, **params: str) -> RedirectResponse:
    # /app/studio is a flat page (no [siteId] route segment exists in the
    # Studio frontend) — the active site is carried as a query param, not a
    # path segment, so this must never become f"/app/studio/{site_id}".
    all_params = dict(params)
    if site_id:
        all_params["site_id"] = str(site_id)
    base = settings.PUBLIC_APP_BASE_URL.rstrip("/")
    query = f"?{urlencode(all_params)}" if all_params else ""
    return RedirectResponse(url=f"{base}/app/studio{query}", status_code=status.HTTP_302_FOUND)


@router.get(
    "/{site_id}/github",
    response_model=GitHubConnectionResponse,
    summary="Get the GitHub connection for a site (owners/admins only)",
)
def get_connection(
    site_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: GitHubService = Depends(get_github_service),
):
    return service.get_connection(user, site_id)


@router.get(
    "/{site_id}/github/connect",
    response_model=GitHubConnectStartResponse,
    summary="Start the GitHub App installation flow (owners/admins only)",
)
def start_connect(
    site_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: GitHubService = Depends(get_github_service),
):
    return service.start_connect(user, site_id)


@router.get(
    "/github/callback",
    summary="GitHub App installation callback (public — GitHub redirects here)",
    include_in_schema=False,
)
async def github_callback(
    installation_id: Optional[str] = Query(default=None),
    setup_action: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    service: GitHubService = Depends(get_github_service),
):
    result = await service.handle_callback(
        installation_id=installation_id, setup_action=setup_action, state=state
    )
    if result.ok:
        return _frontend_redirect(site_id=result.site_id, github="connected")
    return _frontend_redirect(site_id=result.site_id, github_error=result.error or "unknown")


@router.get(
    "/{site_id}/github/repositories",
    response_model=GitHubRepositoryListResponse,
    summary="List repositories accessible to the connected installation (owners/admins only)",
)
async def list_repositories(
    site_id: UUID,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    user: UserProfileResponse = Depends(get_current_user),
    service: GitHubService = Depends(get_github_service),
):
    return await service.list_repositories(user, site_id, page=page, per_page=per_page)


@router.get(
    "/{site_id}/github/branches",
    response_model=GitHubBranchListResponse,
    summary="List branches for a repository (owners/admins only)",
)
async def list_branches(
    site_id: UUID,
    owner: str = Query(...),
    repo: str = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=100),
    user: UserProfileResponse = Depends(get_current_user),
    service: GitHubService = Depends(get_github_service),
):
    return await service.list_branches(user, site_id, owner=owner, repo=repo, page=page, per_page=per_page)


@router.post(
    "/{site_id}/github/select",
    response_model=GitHubConnectionResponse,
    summary="Select a repository + branch to connect to this site (owners/admins only)",
)
async def select_repository(
    site_id: UUID,
    payload: GitHubSelectRepositoryRequest,
    user: UserProfileResponse = Depends(get_current_user),
    service: GitHubService = Depends(get_github_service),
):
    return await service.select_repository(user, site_id, payload)


@router.delete(
    "/{site_id}/github",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect GitHub from this site (owners/admins only)",
)
def disconnect(
    site_id: UUID,
    user: UserProfileResponse = Depends(get_current_user),
    service: GitHubService = Depends(get_github_service),
):
    service.disconnect(user, site_id)
    return None
