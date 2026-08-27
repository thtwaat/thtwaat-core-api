"""Unit tests for app/static_sites/github_service.py — RBAC, company
isolation, connect/callback state handling, repository re-validation, and
audit logging for THTWAAT Deploy Phase 5. Mirrors
tests/unit/static_sites/test_env_vars_service.py's MagicMock(db)/
MagicMock(repo) style; GitHub network calls are mocked via AsyncMock on the
github_client module (never real network access)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.apps.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401
import app.storage.model  # noqa: F401
import app.users.model  # noqa: F401

from app.static_sites import github_client
from app.static_sites.github_client import GitHubApiError
from app.static_sites.github_service import GitHubService
from app.static_sites.models import GitHubConnection, GitHubOAuthState, StaticSite
from app.static_sites.schemas import GitHubSelectRepositoryRequest

TOKEN_MARKER = "ghs_secretinstallationtoken999"


def _profile(role: str = "admin", *, company_id=None, user_id=None):
    return SimpleNamespace(
        id=str(user_id or uuid4()), email="user@example.com", role=role, company_id=str(company_id or uuid4())
    )


def _site(workspace_id, site_id=None) -> StaticSite:
    return StaticSite(id=site_id or uuid4(), workspace_id=workspace_id, name="Acme", slug="acme")


def _stamp(row):
    if getattr(row, "id", None) is None:
        row.id = uuid4()
    if getattr(row, "created_at", None) is None:
        row.created_at = datetime.now(timezone.utc)
    if getattr(row, "updated_at", None) is None:
        row.updated_at = datetime.now(timezone.utc)
    return row


def _connection(*, workspace_id, site_id, installation_id="1001", **overrides) -> GitHubConnection:
    base = dict(
        id=uuid4(), workspace_id=workspace_id, site_id=site_id,
        installation_id=installation_id, github_account_id="55", github_username="octocat",
        account_type="User", repository_owner=None, repository_name=None, repository_id=None,
        default_branch=None, selected_branch=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return GitHubConnection(**base)


def _state_row(*, user_id, workspace_id, site_id, expires_delta=None):
    from datetime import timedelta

    return GitHubOAuthState(
        id=uuid4(),
        state_hash="hash",
        user_id=user_id,
        workspace_id=workspace_id,
        site_id=site_id,
        expires_at=datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15)),
        consumed_at=datetime.now(timezone.utc),
    )


def _service() -> GitHubService:
    svc = GitHubService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.create_github_oauth_state.side_effect = _stamp
    svc.repo.upsert_github_connection.side_effect = _stamp
    return svc


# ---- RBAC ---------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer", "manager", "developer"])
def test_non_manager_roles_cannot_get_connection(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        svc.get_connection(_profile(role), uuid4())
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer"])
def test_non_manager_roles_cannot_start_connect(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        svc.start_connect(_profile(role), uuid4())
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer"])
async def test_non_manager_roles_cannot_list_repositories(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        await svc.list_repositories(_profile(role), uuid4())
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer"])
async def test_non_manager_roles_cannot_select_repository(role):
    svc = _service()
    payload = GitHubSelectRepositoryRequest(repository_owner="o", repository_name="r", branch="main")
    with pytest.raises(HTTPException) as exc:
        await svc.select_repository(_profile(role), uuid4(), payload)
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer"])
def test_non_manager_roles_cannot_disconnect(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        svc.disconnect(_profile(role), uuid4())
    assert exc.value.status_code == 403


# ---- company isolation ---------------------------------------------------------


@pytest.mark.unit
def test_get_connection_cross_company_site_returns_404():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.get_connection(_profile("admin"), uuid4())
    assert exc.value.status_code == 404


@pytest.mark.unit
async def test_select_repository_cross_company_site_returns_404():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    payload = GitHubSelectRepositoryRequest(repository_owner="o", repository_name="r", branch="main")
    with pytest.raises(HTTPException) as exc:
        await svc.select_repository(_profile("admin"), uuid4(), payload)
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_disconnect_cross_company_site_returns_404():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.disconnect(_profile("admin"), uuid4())
    assert exc.value.status_code == 404


# ---- start_connect / state ------------------------------------------------------


@pytest.mark.unit
def test_start_connect_requires_app_configured(monkeypatch):
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)

    def _boom():
        raise HTTPException(status_code=503, detail="GitHub integration is not configured")

    monkeypatch.setattr(github_client, "require_app_configured", _boom)
    with pytest.raises(HTTPException) as exc:
        svc.start_connect(_profile("admin", company_id=company_id), site_id)
    assert exc.value.status_code == 503
    svc.repo.create_github_oauth_state.assert_not_called()


@pytest.mark.unit
def test_start_connect_binds_state_to_user_workspace_site(monkeypatch):
    svc = _service()
    company_id, site_id, user_id = uuid4(), uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)

    monkeypatch.setattr(github_client, "require_app_configured", lambda: None)
    monkeypatch.setattr(github_client, "new_state", lambda: "raw-state")
    monkeypatch.setattr(github_client, "hash_state", lambda s: f"hashed-{s}")
    monkeypatch.setattr(github_client, "build_installation_url", lambda *, state: f"https://github.com/install?state={state}")

    resp = svc.start_connect(_profile("admin", company_id=company_id, user_id=user_id), site_id)

    assert resp.authorize_url == "https://github.com/install?state=raw-state"
    saved = svc.repo.create_github_oauth_state.call_args[0][0]
    assert saved.state_hash == "hashed-raw-state"
    assert str(saved.user_id) == str(user_id)
    assert saved.workspace_id == company_id
    assert saved.site_id == site_id


# ---- handle_callback (public, no bearer auth) ------------------------------------


@pytest.mark.unit
async def test_callback_missing_state_rejected():
    svc = _service()
    result = await svc.handle_callback(installation_id="1", setup_action="install", state=None)
    assert result.ok is False
    assert result.error == "invalid_state"
    svc.repo.consume_github_oauth_state.assert_not_called()


@pytest.mark.unit
async def test_callback_invalid_expired_or_replayed_state_rejected(monkeypatch):
    svc = _service()
    svc.repo.consume_github_oauth_state.return_value = None
    result = await svc.handle_callback(installation_id="1", setup_action="install", state="bad-or-reused")
    assert result.ok is False
    assert result.error == "invalid_state"


@pytest.mark.unit
async def test_callback_pending_org_approval_does_not_create_connection():
    svc = _service()
    site_id = uuid4()
    svc.repo.consume_github_oauth_state.return_value = _state_row(
        user_id=uuid4(), workspace_id=uuid4(), site_id=site_id
    )
    result = await svc.handle_callback(installation_id=None, setup_action="request", state="s")
    assert result.ok is False
    assert result.error == "pending_approval"
    assert result.site_id == site_id
    svc.repo.upsert_github_connection.assert_not_called()


@pytest.mark.unit
async def test_callback_missing_installation_id_rejected():
    svc = _service()
    svc.repo.consume_github_oauth_state.return_value = _state_row(
        user_id=uuid4(), workspace_id=uuid4(), site_id=uuid4()
    )
    result = await svc.handle_callback(installation_id=None, setup_action="install", state="s")
    assert result.ok is False
    assert result.error == "missing_installation"


@pytest.mark.unit
async def test_callback_github_api_failure_surfaces_generic_error(monkeypatch):
    svc = _service()
    svc.repo.consume_github_oauth_state.return_value = _state_row(
        user_id=uuid4(), workspace_id=uuid4(), site_id=uuid4()
    )
    monkeypatch.setattr(
        github_client, "get_installation", AsyncMock(side_effect=GitHubApiError(status_code=503, detail="down"))
    )
    result = await svc.handle_callback(installation_id="1", setup_action="install", state="s")
    assert result.ok is False
    assert result.error == "github_unavailable"


@pytest.mark.unit
async def test_callback_suspended_installation_rejected(monkeypatch):
    svc = _service()
    svc.repo.consume_github_oauth_state.return_value = _state_row(
        user_id=uuid4(), workspace_id=uuid4(), site_id=uuid4()
    )
    monkeypatch.setattr(
        github_client,
        "get_installation",
        AsyncMock(return_value={"suspended_at": "2026-01-01T00:00:00Z", "account": {"id": 1, "login": "x"}}),
    )
    result = await svc.handle_callback(installation_id="1", setup_action="install", state="s")
    assert result.ok is False
    assert result.error == "installation_suspended"


@pytest.mark.unit
async def test_callback_success_creates_connection_with_no_token_fields(monkeypatch):
    svc = _service()
    user_id, workspace_id, site_id = uuid4(), uuid4(), uuid4()
    svc.repo.consume_github_oauth_state.return_value = _state_row(
        user_id=user_id, workspace_id=workspace_id, site_id=site_id
    )
    svc.repo.get_github_connection.return_value = None
    monkeypatch.setattr(
        github_client,
        "get_installation",
        AsyncMock(return_value={"account": {"id": 777, "login": "octocat", "type": "User"}}),
    )

    result = await svc.handle_callback(installation_id="42", setup_action="install", state="s")

    assert result.ok is True
    assert result.site_id == site_id
    saved = svc.repo.upsert_github_connection.call_args[0][0]
    assert saved.installation_id == "42"
    assert saved.github_username == "octocat"
    assert saved.created_by == user_id
    # Structural proof there is no token field to leak in the first place.
    assert not hasattr(saved, "access_token")
    assert not hasattr(saved, "refresh_token")
    assert not hasattr(saved, "encrypted_access_token")


@pytest.mark.unit
async def test_callback_reconnect_with_different_installation_clears_prior_repo_selection(monkeypatch):
    svc = _service()
    user_id, workspace_id, site_id = uuid4(), uuid4(), uuid4()
    svc.repo.consume_github_oauth_state.return_value = _state_row(
        user_id=user_id, workspace_id=workspace_id, site_id=site_id
    )
    existing = _connection(
        workspace_id=workspace_id, site_id=site_id, installation_id="OLD",
        repository_owner="acme", repository_name="app", repository_id="9", default_branch="main", selected_branch="main",
    )
    svc.repo.get_github_connection.return_value = existing
    monkeypatch.setattr(
        github_client, "get_installation", AsyncMock(return_value={"account": {"id": 2, "login": "someone-else"}})
    )

    await svc.handle_callback(installation_id="NEW", setup_action="update", state="s")

    saved = svc.repo.upsert_github_connection.call_args[0][0]
    assert saved.installation_id == "NEW"
    assert saved.repository_owner is None
    assert saved.selected_branch is None


@pytest.mark.unit
async def test_callback_writes_audit_log_without_token_metadata(monkeypatch):
    svc = _service()
    user_id, workspace_id, site_id = uuid4(), uuid4(), uuid4()
    svc.repo.consume_github_oauth_state.return_value = _state_row(
        user_id=user_id, workspace_id=workspace_id, site_id=site_id
    )
    svc.repo.get_github_connection.return_value = None
    monkeypatch.setattr(
        github_client, "get_installation", AsyncMock(return_value={"account": {"id": 1, "login": "octocat"}})
    )

    audited = {}

    def _fake_audit(self, **kwargs):
        audited.update(kwargs)

    monkeypatch.setattr(GitHubService, "_audit", _fake_audit)

    await svc.handle_callback(installation_id="42", setup_action="install", state="s")

    assert audited["action"] == "github.connected"
    dumped = str(audited["metadata"])
    assert "token" not in dumped.lower()


# ---- repository / branch listing -------------------------------------------------


@pytest.mark.unit
async def test_list_repositories_requires_existing_connection():
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_github_connection.return_value = None
    with pytest.raises(HTTPException) as exc:
        await svc.list_repositories(_profile("admin", company_id=company_id), site_id)
    assert exc.value.status_code == 404


@pytest.mark.unit
async def test_list_repositories_returns_safe_metadata_only(monkeypatch):
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    conn = _connection(workspace_id=company_id, site_id=site_id)
    svc.repo.get_github_connection.return_value = conn

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value=TOKEN_MARKER))
    monkeypatch.setattr(
        github_client,
        "list_installation_repositories",
        AsyncMock(
            return_value={
                "repositories": [
                    {"id": 1, "name": "app", "full_name": "octocat/app", "private": True,
                     "default_branch": "main", "owner": {"login": "octocat"}}
                ]
            }
        ),
    )

    resp = await svc.list_repositories(_profile("admin", company_id=company_id), site_id)
    assert len(resp.items) == 1
    assert resp.items[0].full_name == "octocat/app"
    dumped = resp.model_dump_json()
    assert TOKEN_MARKER not in dumped


@pytest.mark.unit
async def test_list_branches_requires_existing_connection():
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_github_connection.return_value = None
    with pytest.raises(HTTPException) as exc:
        await svc.list_branches(_profile("admin", company_id=company_id), site_id, owner="o", repo="r")
    assert exc.value.status_code == 404


@pytest.mark.unit
async def test_list_branches_propagates_repo_not_accessible_as_404(monkeypatch):
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_github_connection.return_value = _connection(workspace_id=company_id, site_id=site_id)

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value=TOKEN_MARKER))
    monkeypatch.setattr(
        github_client, "list_branches", AsyncMock(side_effect=GitHubApiError(status_code=404, detail="not found"))
    )

    with pytest.raises(GitHubApiError) as exc:
        await svc.list_branches(_profile("admin", company_id=company_id), site_id, owner="other", repo="private-repo")
    assert exc.value.status_code == 404


# ---- select_repository -----------------------------------------------------------


@pytest.mark.unit
async def test_select_repository_requires_existing_connection():
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_github_connection.return_value = None
    payload = GitHubSelectRepositoryRequest(repository_owner="o", repository_name="r", branch="main")
    with pytest.raises(HTTPException) as exc:
        await svc.select_repository(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 404


@pytest.mark.unit
async def test_select_repository_revalidates_against_github_before_persisting(monkeypatch):
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    conn = _connection(workspace_id=company_id, site_id=site_id)
    svc.repo.get_github_connection.return_value = conn

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value=TOKEN_MARKER))
    monkeypatch.setattr(
        github_client,
        "get_repository",
        AsyncMock(return_value={"id": 99, "name": "app", "default_branch": "main", "owner": {"login": "octocat"}}),
    )
    monkeypatch.setattr(github_client, "get_branch", AsyncMock(return_value={"name": "main"}))

    payload = GitHubSelectRepositoryRequest(repository_owner="octocat", repository_name="app", branch="main")
    resp = await svc.select_repository(_profile("admin", company_id=company_id), site_id, payload)

    assert resp.repository_owner == "octocat"
    assert resp.repository_id == "99"
    assert resp.selected_branch == "main"
    github_client.get_repository.assert_awaited_once()
    github_client.get_branch.assert_awaited_once()


@pytest.mark.unit
async def test_select_repository_rejects_repo_outside_installation(monkeypatch):
    """A repo the installation was never granted access to must 404 from
    GitHub's own installation-token scoping, not be silently accepted."""
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    conn = _connection(workspace_id=company_id, site_id=site_id)
    svc.repo.get_github_connection.return_value = conn

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value=TOKEN_MARKER))
    monkeypatch.setattr(
        github_client, "get_repository", AsyncMock(side_effect=GitHubApiError(status_code=404, detail="not found"))
    )

    payload = GitHubSelectRepositoryRequest(repository_owner="someone-else", repository_name="private-repo", branch="main")
    with pytest.raises(GitHubApiError) as exc:
        await svc.select_repository(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 404
    svc.repo.upsert_github_connection.assert_not_called()


@pytest.mark.unit
async def test_select_repository_rejects_branch_that_does_not_exist(monkeypatch):
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    conn = _connection(workspace_id=company_id, site_id=site_id)
    svc.repo.get_github_connection.return_value = conn

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value=TOKEN_MARKER))
    monkeypatch.setattr(
        github_client,
        "get_repository",
        AsyncMock(return_value={"id": 99, "name": "app", "default_branch": "main", "owner": {"login": "octocat"}}),
    )
    monkeypatch.setattr(
        github_client, "get_branch", AsyncMock(side_effect=GitHubApiError(status_code=404, detail="not found"))
    )

    payload = GitHubSelectRepositoryRequest(repository_owner="octocat", repository_name="app", branch="does-not-exist")
    with pytest.raises(GitHubApiError) as exc:
        await svc.select_repository(_profile("admin", company_id=company_id), site_id, payload)
    assert exc.value.status_code == 404
    svc.repo.upsert_github_connection.assert_not_called()


# ---- disconnect ---------------------------------------------------------------------


@pytest.mark.unit
def test_disconnect_requires_existing_connection():
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    svc.repo.get_github_connection.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc.disconnect(_profile("admin", company_id=company_id), site_id)
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_disconnect_deletes_row_and_audits_without_calling_github(monkeypatch):
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    conn = _connection(
        workspace_id=company_id, site_id=site_id, repository_owner="acme", repository_name="app"
    )
    svc.repo.get_github_connection.return_value = conn

    spies = {name: MagicMock() for name in dir(github_client) if not name.startswith("_")}
    for name, spy in spies.items():
        if callable(getattr(github_client, name, None)):
            monkeypatch.setattr(github_client, name, spy)

    svc.disconnect(_profile("admin", company_id=company_id), site_id)

    svc.repo.delete_github_connection.assert_called_once_with(conn)
    for name, spy in spies.items():
        spy.assert_not_called()


@pytest.mark.unit
def test_disconnect_repository_does_not_reach_github_repository_delete_api(monkeypatch):
    """Explicit regression: disconnecting from THTWAAT must never delete the
    user's actual GitHub repository (task requirement)."""
    svc = _service()
    company_id, site_id = uuid4(), uuid4()
    svc.repo.get_site_for_workspace.return_value = _site(company_id, site_id)
    conn = _connection(workspace_id=company_id, site_id=site_id)
    svc.repo.get_github_connection.return_value = conn
    assert not hasattr(github_client, "delete_repository")
    assert not hasattr(github_client, "uninstall_installation")

    svc.disconnect(_profile("admin", company_id=company_id), site_id)
    svc.repo.delete_github_connection.assert_called_once()
