"""Router-level tests for /api/v2/studio/static-sites/{site_id}/github —
real HTTP requests through FastAPI's TestClient, GitHubService mocked out
(mirrors tests/unit/static_sites/test_env_vars_router.py's dependency-
override style)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.router import get_current_user
from app.static_sites.github_router import get_github_service, router
from app.static_sites.github_service import GitHubCallbackResult
from app.static_sites.schemas import (
    GitHubBranchListResponse,
    GitHubBranchResponse,
    GitHubConnectionResponse,
    GitHubConnectStartResponse,
    GitHubRepositoryListResponse,
    GitHubRepositoryResponse,
)

TOKEN_MARKER = "ghs_shouldneverappear987"


def _profile(role: str = "admin"):
    return SimpleNamespace(id=str(uuid4()), email="user@example.com", role=role, company_id=str(uuid4()))


def _fake_connection(**overrides) -> GitHubConnectionResponse:
    base = dict(
        id=uuid4(), site_id=uuid4(), connected=True, github_account_id="55", github_username="octocat",
        account_type="User", installation_id="1001", repository_owner=None, repository_name=None,
        repository_id=None, default_branch=None, selected_branch=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return GitHubConnectionResponse(**base)


@pytest.fixture
def app_and_client():
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    fastapi_app.dependency_overrides[get_current_user] = lambda: _profile("admin")
    fake_service = MagicMock()
    fastapi_app.dependency_overrides[get_github_service] = lambda: fake_service
    client = TestClient(fastapi_app, follow_redirects=False)
    yield fastapi_app, client, fake_service
    fastapi_app.dependency_overrides.clear()


# ---- auth / RBAC ------------------------------------------------------------


@pytest.mark.unit
def test_get_connection_requires_authentication():
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)

    def _deny():
        raise HTTPException(status_code=401, detail="Not authenticated")

    fastapi_app.dependency_overrides[get_current_user] = _deny
    client = TestClient(fastapi_app)
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github")
    assert resp.status_code == 401


@pytest.mark.unit
def test_start_connect_forbidden_for_non_manager_propagates(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.start_connect.side_effect = HTTPException(
        status_code=403, detail="Only company owners and admins can manage the GitHub connection"
    )
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github/connect")
    assert resp.status_code == 403


@pytest.mark.unit
def test_disconnect_forbidden_for_non_manager_propagates(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.disconnect.side_effect = HTTPException(status_code=403, detail="forbidden")
    resp = client.delete(f"/api/v2/studio/static-sites/{uuid4()}/github")
    assert resp.status_code == 403


# ---- get_connection -----------------------------------------------------------


@pytest.mark.unit
def test_get_connection_success_never_leaks_token_like_fields(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.get_connection.return_value = _fake_connection(
        repository_owner="octocat", repository_name="app", default_branch="main", selected_branch="main"
    )
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github")
    assert resp.status_code == 200
    body = resp.json()
    for forbidden in ("access_token", "refresh_token", "client_secret", "token"):
        assert forbidden not in body


@pytest.mark.unit
def test_get_connection_not_connected_returns_404(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.get_connection.side_effect = HTTPException(
        status_code=404, detail="GitHub is not connected for this site"
    )
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github")
    assert resp.status_code == 404


@pytest.mark.unit
def test_get_connection_cross_company_returns_404_not_403(app_and_client):
    """Cross-company access must look identical to 'doesn't exist' — never
    reveal that a connection exists for someone else's site."""
    _app, client, fake_service = app_and_client
    fake_service.get_connection.side_effect = HTTPException(status_code=404, detail="Static site not found")
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github")
    assert resp.status_code == 404


# ---- start_connect --------------------------------------------------------------


@pytest.mark.unit
def test_start_connect_returns_authorize_url_only(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.start_connect.return_value = GitHubConnectStartResponse(
        authorize_url="https://github.com/apps/thtwaat-deploy/installations/new?state=abc"
    )
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github/connect")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"authorize_url"}
    assert "abc" in body["authorize_url"]


@pytest.mark.unit
def test_start_connect_not_configured_returns_503(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.start_connect.side_effect = HTTPException(
        status_code=503, detail="GitHub integration is not configured"
    )
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github/connect")
    assert resp.status_code == 503


# ---- callback (public) -----------------------------------------------------------


@pytest.mark.unit
def test_callback_does_not_require_bearer_auth():
    """GitHub itself hits this endpoint directly — it must not depend on
    get_current_user at all."""
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    fake_service = MagicMock()
    fake_service.handle_callback = AsyncMock(return_value=GitHubCallbackResult(ok=False, error="invalid_state"))
    fastapi_app.dependency_overrides[get_github_service] = lambda: fake_service
    # Deliberately no override for get_current_user.
    client = TestClient(fastapi_app, follow_redirects=False)

    resp = client.get("/api/v2/studio/static-sites/github/callback", params={"state": "x"})
    assert resp.status_code != 401


@pytest.mark.unit
def test_callback_success_redirects_to_site_studio_page(app_and_client):
    _app, client, fake_service = app_and_client
    site_id = uuid4()
    fake_service.handle_callback = AsyncMock(return_value=GitHubCallbackResult(ok=True, site_id=site_id))

    resp = client.get(
        "/api/v2/studio/static-sites/github/callback",
        params={"installation_id": "42", "setup_action": "install", "state": "s"},
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert str(site_id) in location
    assert "github=connected" in location


@pytest.mark.unit
def test_callback_invalid_state_redirects_with_generic_error(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.handle_callback = AsyncMock(return_value=GitHubCallbackResult(ok=False, error="invalid_state"))

    resp = client.get("/api/v2/studio/static-sites/github/callback", params={"state": "bad"})
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "github_error=invalid_state" in location


@pytest.mark.unit
def test_callback_redirect_never_contains_a_token(app_and_client):
    _app, client, fake_service = app_and_client
    site_id = uuid4()
    fake_service.handle_callback = AsyncMock(return_value=GitHubCallbackResult(ok=True, site_id=site_id))

    resp = client.get(
        "/api/v2/studio/static-sites/github/callback",
        params={"installation_id": "42", "setup_action": "install", "state": "s"},
    )
    assert TOKEN_MARKER not in resp.headers["location"]
    assert "token" not in resp.headers["location"].lower()


@pytest.mark.unit
def test_callback_excluded_from_openapi_schema(app_and_client):
    app_, _client, _fake_service = app_and_client
    schema = app_.openapi()
    assert "/api/v2/studio/static-sites/github/callback" not in schema["paths"]


# ---- repositories / branches -----------------------------------------------------


@pytest.mark.unit
def test_list_repositories_success(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.list_repositories = AsyncMock(
        return_value=GitHubRepositoryListResponse(
            items=[
                GitHubRepositoryResponse(
                    repository_id="1", owner="octocat", name="app", full_name="octocat/app",
                    private=True, default_branch="main",
                )
            ],
            page=1,
            per_page=30,
        )
    )
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github/repositories")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["full_name"] == "octocat/app"


@pytest.mark.unit
def test_list_repositories_github_rate_limited_returns_429(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.list_repositories = AsyncMock(
        side_effect=HTTPException(status_code=429, detail="GitHub API rate limit exceeded. Try again later.")
    )
    resp = client.get(f"/api/v2/studio/static-sites/{uuid4()}/github/repositories")
    assert resp.status_code == 429


@pytest.mark.unit
def test_list_branches_success(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.list_branches = AsyncMock(
        return_value=GitHubBranchListResponse(
            items=[GitHubBranchResponse(name="main", protected=True)], page=1, per_page=30
        )
    )
    resp = client.get(
        f"/api/v2/studio/static-sites/{uuid4()}/github/branches", params={"owner": "octocat", "repo": "app"}
    )
    assert resp.status_code == 200
    assert resp.json()["items"][0]["name"] == "main"


@pytest.mark.unit
def test_list_branches_repository_no_longer_exists_returns_404(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.list_branches = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="GitHub resource not found or not accessible.")
    )
    resp = client.get(
        f"/api/v2/studio/static-sites/{uuid4()}/github/branches", params={"owner": "octocat", "repo": "deleted-repo"}
    )
    assert resp.status_code == 404


# ---- select_repository ---------------------------------------------------------------


@pytest.mark.unit
def test_select_repository_success(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.select_repository = AsyncMock(
        return_value=_fake_connection(repository_owner="octocat", repository_name="app", selected_branch="main")
    )
    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/github/select",
        json={"repository_owner": "octocat", "repository_name": "app", "branch": "main"},
    )
    assert resp.status_code == 200
    assert resp.json()["repository_name"] == "app"


@pytest.mark.unit
def test_select_repository_rejects_malformed_owner_before_reaching_service(app_and_client):
    """SSRF/path-injection payloads must be rejected at schema validation,
    never reach GitHubService."""
    _app, client, fake_service = app_and_client
    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/github/select",
        json={"repository_owner": "../evil", "repository_name": "app", "branch": "main"},
    )
    assert resp.status_code == 422
    fake_service.select_repository.assert_not_called()


@pytest.mark.unit
def test_select_repository_not_accessible_returns_404(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.select_repository = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="GitHub resource not found or not accessible.")
    )
    resp = client.post(
        f"/api/v2/studio/static-sites/{uuid4()}/github/select",
        json={"repository_owner": "someone-else", "repository_name": "private-repo", "branch": "main"},
    )
    assert resp.status_code == 404


# ---- disconnect -----------------------------------------------------------------------


@pytest.mark.unit
def test_disconnect_success_returns_204(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.disconnect.return_value = None
    resp = client.delete(f"/api/v2/studio/static-sites/{uuid4()}/github")
    assert resp.status_code == 204
    assert resp.text == ""


@pytest.mark.unit
def test_disconnect_cross_company_returns_404(app_and_client):
    _app, client, fake_service = app_and_client
    fake_service.disconnect.side_effect = HTTPException(status_code=404, detail="Static site not found")
    resp = client.delete(f"/api/v2/studio/static-sites/{uuid4()}/github")
    assert resp.status_code == 404
