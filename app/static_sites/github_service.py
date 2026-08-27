"""GitHubService — THTWAAT Deploy Phase 5 (GitHub Connect).

Auth/company-scoping/RBAC/audit conventions are copied verbatim from
app/static_sites/env_vars_service.py (itself copied from
app/static_sites/service.py) — see _require_github_manager()/_get_site()/
_audit() below. This surface can reveal which repositories a company has
access to, so — like env vars — every method (including reads) is gated
behind the same owner/admin check, not just mutations.

No GitHub access/refresh token is ever handled here (see
app/static_sites/models.py::GitHubConnection and github_client.py's module
docstring) — every GitHub API call mints a short-lived installation token
on demand and discards it after use.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schema import UserProfileResponse
from app.auth.tenant import can_manage_company_users
from app.config.settings import settings
from app.static_sites import github_client
from app.static_sites.github_client import GitHubApiError
from app.static_sites.models import GitHubConnection, GitHubOAuthState, StaticSite
from app.static_sites.repository import StaticSiteRepository
from app.static_sites.schemas import (
    GitHubBranchListResponse,
    GitHubBranchResponse,
    GitHubConnectionResponse,
    GitHubConnectStartResponse,
    GitHubRepositoryListResponse,
    GitHubRepositoryResponse,
    GitHubSelectRepositoryRequest,
)

logger = logging.getLogger(__name__)

_NOT_FOUND_SITE = "Static site not found"
_NOT_CONNECTED = "GitHub is not connected for this site"
_GENERIC_FAILURE_MESSAGE = "GitHub operation failed due to an internal error."


@dataclass
class GitHubCallbackResult:
    ok: bool
    site_id: Optional[UUID] = None
    error: Optional[str] = None


def _to_connection_response(row: GitHubConnection) -> GitHubConnectionResponse:
    return GitHubConnectionResponse(
        id=row.id,
        site_id=row.site_id,
        connected=True,
        github_account_id=row.github_account_id,
        github_username=row.github_username,
        account_type=row.account_type,
        installation_id=row.installation_id,
        repository_owner=row.repository_owner,
        repository_name=row.repository_name,
        repository_id=row.repository_id,
        default_branch=row.default_branch,
        selected_branch=row.selected_branch,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class GitHubService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StaticSiteRepository(db)

    # ---- auth helpers (mirrors app/static_sites/env_vars_service.py) -----

    def _require_github_manager(self, user: UserProfileResponse) -> None:
        if not can_manage_company_users(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company owners and admins can manage the GitHub connection",
            )

    def _get_site(self, user: UserProfileResponse, site_id: UUID) -> StaticSite:
        site = self.repo.get_site_for_workspace(site_id, UUID(str(user.company_id)))
        if not site:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_SITE)
        return site

    def _get_connection(self, site: StaticSite) -> GitHubConnection:
        row = self.repo.get_github_connection(site.id, site.workspace_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_CONNECTED)
        return row

    def _audit(
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

            # metadata deliberately carries only non-secret identifiers
            # (site_id, github_username, installation_id, repository owner/
            # name, branch) — never a token, code, or private key.
            EnterpriseService(self.db).audit(
                company_id,
                actor_id,
                action=action,
                resource_type="github_connection",
                resource_id=resource_id,
                severity=AuditSeverity.INFO,
                metadata=metadata or {},
                commit=True,
            )
        except Exception:  # noqa: BLE001
            logger.warning("github_connection_audit_failed action=%s", action)

    @staticmethod
    def _actor_id(user: UserProfileResponse) -> UUID:
        return UUID(str(user.id))

    # ---- connection status --------------------------------------------------

    def get_connection(self, user: UserProfileResponse, site_id: UUID) -> GitHubConnectionResponse:
        self._require_github_manager(user)
        site = self._get_site(user, site_id)
        row = self._get_connection(site)
        return _to_connection_response(row)

    # ---- connect / authorize -------------------------------------------------

    def start_connect(self, user: UserProfileResponse, site_id: UUID) -> GitHubConnectStartResponse:
        self._require_github_manager(user)
        site = self._get_site(user, site_id)
        github_client.require_app_configured()

        raw_state = github_client.new_state()
        state_row = GitHubOAuthState(
            state_hash=github_client.hash_state(raw_state),
            user_id=self._actor_id(user),
            workspace_id=site.workspace_id,
            site_id=site.id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.GITHUB_OAUTH_STATE_TTL_MINUTES),
        )
        self.repo.create_github_oauth_state(state_row)
        url = github_client.build_installation_url(state=raw_state)
        return GitHubConnectStartResponse(authorize_url=url)

    async def handle_callback(
        self,
        *,
        installation_id: Optional[str],
        setup_action: Optional[str],
        state: Optional[str],
    ) -> GitHubCallbackResult:
        """Public entry point (no bearer auth — GitHub itself hits this).
        Identity/workspace/site come entirely from the consumed state row,
        never from anything the request itself claims."""
        if not state:
            return GitHubCallbackResult(ok=False, error="invalid_state")

        state_row = self.repo.consume_github_oauth_state(github_client.hash_state(state))
        if not state_row:
            # Deliberately the same generic error for mismatch/expiry/replay —
            # distinguishing them would give an attacker an oracle.
            return GitHubCallbackResult(ok=False, error="invalid_state")

        site_id = state_row.site_id
        workspace_id = state_row.workspace_id
        user_id = state_row.user_id

        if setup_action == "request":
            # Org installation pending owner approval — nothing to persist yet.
            return GitHubCallbackResult(ok=False, site_id=site_id, error="pending_approval")

        if not installation_id:
            return GitHubCallbackResult(ok=False, site_id=site_id, error="missing_installation")

        try:
            installation = await github_client.get_installation(str(installation_id))
        except GitHubApiError:
            return GitHubCallbackResult(ok=False, site_id=site_id, error="github_unavailable")

        if installation.get("suspended_at"):
            return GitHubCallbackResult(ok=False, site_id=site_id, error="installation_suspended")

        account = installation.get("account") or {}
        github_account_id = str(account.get("id") or "")
        github_username = str(account.get("login") or "")
        account_type = account.get("type")
        if not github_account_id or not github_username:
            return GitHubCallbackResult(ok=False, site_id=site_id, error="github_unavailable")

        existing = self.repo.get_github_connection(site_id, workspace_id)
        if existing:
            row = existing
            if row.installation_id != str(installation_id):
                # A different GitHub account/installation was connected —
                # any previously selected repo/branch is no longer valid.
                row.repository_owner = None
                row.repository_name = None
                row.repository_id = None
                row.default_branch = None
                row.selected_branch = None
        else:
            row = GitHubConnection(workspace_id=workspace_id, site_id=site_id)

        row.installation_id = str(installation_id)
        row.github_account_id = github_account_id
        row.github_username = github_username
        row.account_type = account_type
        row.created_by = user_id

        try:
            row = self.repo.upsert_github_connection(row)
        except Exception:  # noqa: BLE001
            self.db.rollback()
            logger.exception("github_connection_save_failed site_id=%s", site_id)
            return GitHubCallbackResult(ok=False, site_id=site_id, error="internal_error")

        self._audit(
            company_id=workspace_id,
            actor_id=user_id,
            action="github.connected",
            resource_id=str(row.id),
            metadata={
                "site_id": str(site_id),
                "github_username": github_username,
                "installation_id": row.installation_id,
            },
        )
        return GitHubCallbackResult(ok=True, site_id=site_id)

    # ---- repository / branch listing -----------------------------------------

    async def list_repositories(
        self, user: UserProfileResponse, site_id: UUID, *, page: int = 1, per_page: int = 30
    ) -> GitHubRepositoryListResponse:
        self._require_github_manager(user)
        site = self._get_site(user, site_id)
        connection = self._get_connection(site)

        token = await github_client.mint_installation_token(connection.installation_id)
        data = await github_client.list_installation_repositories(token, page=page, per_page=per_page)
        items = [
            GitHubRepositoryResponse(
                repository_id=str(r.get("id")),
                owner=(r.get("owner") or {}).get("login", ""),
                name=r.get("name", ""),
                full_name=r.get("full_name", ""),
                private=bool(r.get("private", False)),
                default_branch=r.get("default_branch"),
            )
            for r in (data.get("repositories") or [])
        ]
        return GitHubRepositoryListResponse(items=items, page=page, per_page=per_page)

    async def list_branches(
        self,
        user: UserProfileResponse,
        site_id: UUID,
        *,
        owner: str,
        repo: str,
        page: int = 1,
        per_page: int = 30,
    ) -> GitHubBranchListResponse:
        self._require_github_manager(user)
        site = self._get_site(user, site_id)
        connection = self._get_connection(site)

        token = await github_client.mint_installation_token(connection.installation_id)
        # GitHub itself enforces that the installation token can only see
        # repos actually granted to the installation — an out-of-scope
        # owner/repo 404s here rather than leaking branch data.
        branches = await github_client.list_branches(token, owner, repo, page=page, per_page=per_page)
        items = [
            GitHubBranchResponse(name=b.get("name", ""), protected=bool(b.get("protected", False)))
            for b in branches
        ]
        return GitHubBranchListResponse(items=items, page=page, per_page=per_page)

    # ---- repository selection -------------------------------------------------

    async def select_repository(
        self, user: UserProfileResponse, site_id: UUID, payload: GitHubSelectRepositoryRequest
    ) -> GitHubConnectionResponse:
        self._require_github_manager(user)
        site = self._get_site(user, site_id)
        connection = self._get_connection(site)

        token = await github_client.mint_installation_token(connection.installation_id)
        # Re-verify against GitHub using the installation's own token —
        # never trust the client-supplied owner/repo/branch blindly. A repo
        # not accessible to this installation 404s here (GitHubApiError),
        # closing "repository confusion"/"unauthorized repository selection".
        repo_data = await github_client.get_repository(token, payload.repository_owner, payload.repository_name)
        await github_client.get_branch(token, payload.repository_owner, payload.repository_name, payload.branch)

        connection.repository_owner = (repo_data.get("owner") or {}).get("login", payload.repository_owner)
        connection.repository_name = repo_data.get("name", payload.repository_name)
        connection.repository_id = str(repo_data.get("id") or "")
        connection.default_branch = repo_data.get("default_branch")
        connection.selected_branch = payload.branch

        try:
            connection = self.repo.upsert_github_connection(connection)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("github_connection_select_failed site_id=%s", site.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_GENERIC_FAILURE_MESSAGE
            ) from exc

        self._audit(
            company_id=site.workspace_id,
            actor_id=self._actor_id(user),
            action="github.repository_selected",
            resource_id=str(connection.id),
            metadata={
                "site_id": str(site.id),
                "repository_owner": connection.repository_owner,
                "repository_name": connection.repository_name,
                "branch": connection.selected_branch,
            },
        )
        return _to_connection_response(connection)

    # ---- disconnect ------------------------------------------------------------

    def disconnect(self, user: UserProfileResponse, site_id: UUID) -> None:
        self._require_github_manager(user)
        site = self._get_site(user, site_id)
        connection = self._get_connection(site)

        metadata = {
            "site_id": str(site.id),
            "github_username": connection.github_username,
            "installation_id": connection.installation_id,
            "repository_owner": connection.repository_owner,
            "repository_name": connection.repository_name,
        }
        connection_id = str(connection.id)

        try:
            self.repo.delete_github_connection(connection)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.exception("github_connection_disconnect_failed site_id=%s", site.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_GENERIC_FAILURE_MESSAGE
            ) from exc

        self._audit(
            company_id=site.workspace_id,
            actor_id=self._actor_id(user),
            action="github.disconnected",
            resource_id=connection_id,
            metadata=metadata,
        )
