"""Unit tests for StaticSiteService's THTWAAT Deploy Phase 5C additions —
create_github_deployment() (the fast webhook-request path) and
run_github_deploy() (the async worker entrypoint), plus the
_mark_if_superseded() stale-commit/concurrency guard. Mirrors
test_idempotency.py's MagicMock(repo) style; GitHub network calls are
mocked via AsyncMock on the github_client module (never real network)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.apps.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401
import app.storage.model  # noqa: F401
import app.users.model  # noqa: F401

from app.static_sites import github_client
from app.static_sites.models import GitHubConnection, StaticSite, StaticSiteDeployment
from app.static_sites.service import StaticSiteService

COMMIT_SHA = "a" * 40


def _stamp(row):
    defaults = {
        "id": lambda: uuid4(), "instructions": lambda: [], "logs": lambda: [], "urls": lambda: {},
        "health": lambda: {}, "ssl": lambda: {}, "duration_ms": lambda: 0, "retryable": lambda: False,
        "file_count": lambda: 0, "total_bytes": lambda: 0, "upload_size_bytes": lambda: 0,
        "is_current": lambda: True, "live": lambda: False, "environment": lambda: "production",
        "provider": lambda: "static", "status": lambda: "queued", "stage": lambda: "queued",
        "created_at": lambda: datetime.now(timezone.utc), "updated_at": lambda: datetime.now(timezone.utc),
    }
    for field, factory in defaults.items():
        if getattr(row, field, None) is None:
            setattr(row, field, factory())
    return row


def _service() -> StaticSiteService:
    svc = StaticSiteService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.create_deployment.side_effect = _stamp
    svc.repo.save_deployment.side_effect = _stamp
    return svc


def _site(workspace_id=None, site_id=None) -> StaticSite:
    return StaticSite(id=site_id or uuid4(), workspace_id=workspace_id or uuid4(), name="Demo", slug="demo")


def _connection(*, workspace_id, site_id, created_by=None) -> GitHubConnection:
    return GitHubConnection(
        id=uuid4(), workspace_id=workspace_id, site_id=site_id,
        installation_id="42", github_account_id="1", github_username="octocat", account_type="User",
        repository_owner="octocat", repository_name="app", repository_id="555",
        default_branch="main", selected_branch="main", created_by=created_by,
    )


def _deployment(*, site_id, workspace_id, version, **overrides) -> StaticSiteDeployment:
    base = dict(
        id=uuid4(), site_id=site_id, workspace_id=workspace_id, version=version,
        source_type="zip", environment="production", status="completed", stage="completed",
        is_current=True,
    )
    base.update(overrides)
    return _stamp(StaticSiteDeployment(**base))


# ---- create_github_deployment ------------------------------------------------


@pytest.mark.unit
def test_create_github_deployment_pins_exact_commit_and_source_metadata():
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    svc.repo.next_deployment_version.return_value = 3

    row = svc.create_github_deployment(site=site, connection=connection, commit_sha=COMMIT_SHA, branch="main")

    assert row.source_provider == "github"
    assert row.source_type == "zip"
    assert row.github_commit_sha == COMMIT_SHA
    assert row.github_branch == "main"
    assert row.github_repository_owner == "octocat"
    assert row.github_repository_name == "app"
    assert row.is_current is True
    svc.repo.clear_current_deployments.assert_called_once_with(site.id)


@pytest.mark.unit
def test_create_github_deployment_uses_connections_trusted_owner_name_not_arbitrary_input():
    """The repository owner/name recorded on the deployment must come from
    the STORED GitHubConnection (already re-verified against GitHub at
    select_repository time), never anything passed in directly — this
    method's signature doesn't even accept a raw owner/name string."""
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    connection.repository_owner = "trusted-owner"
    connection.repository_name = "trusted-repo"
    svc.repo.next_deployment_version.return_value = 1

    row = svc.create_github_deployment(site=site, connection=connection, commit_sha=COMMIT_SHA, branch="main")

    assert row.github_repository_owner == "trusted-owner"
    assert row.github_repository_name == "trusted-repo"


@pytest.mark.unit
def test_create_github_deployment_audits_without_leaking_token(monkeypatch):
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    svc.repo.next_deployment_version.return_value = 1

    audited = {}
    monkeypatch.setattr(StaticSiteService, "_audit", lambda self, **kw: audited.update(kw))

    svc.create_github_deployment(site=site, connection=connection, commit_sha=COMMIT_SHA, branch="main")

    assert audited["action"] == "static_deploy.github_push"
    dumped = str(audited["metadata"])
    assert "token" not in dumped.lower()
    assert COMMIT_SHA in dumped


# ---- _mark_if_superseded ----------------------------------------------------


@pytest.mark.unit
def test_mark_if_superseded_false_when_no_current():
    svc = _service()
    row = _deployment(site_id=uuid4(), workspace_id=uuid4(), version=1)
    assert svc._mark_if_superseded(row, None) is False


@pytest.mark.unit
def test_mark_if_superseded_false_when_current_is_self():
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    row = _deployment(site_id=site_id, workspace_id=workspace_id, version=2)
    assert svc._mark_if_superseded(row, row) is False


@pytest.mark.unit
def test_mark_if_superseded_false_when_current_is_older_or_equal_version():
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    row = _deployment(site_id=site_id, workspace_id=workspace_id, version=5)
    older = _deployment(site_id=site_id, workspace_id=workspace_id, version=3)
    assert svc._mark_if_superseded(row, older) is False


@pytest.mark.unit
def test_mark_if_superseded_true_when_a_newer_version_is_current():
    """The core stale-commit protection (spec §13): a deployment for an
    older commit must never activate after a newer commit already became
    current."""
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    row = _deployment(site_id=site_id, workspace_id=workspace_id, version=5, is_current=True)
    newer = _deployment(site_id=site_id, workspace_id=workspace_id, version=6)

    result = svc._mark_if_superseded(row, newer)

    assert result is True
    assert row.is_current is False
    assert row.status == "completed"
    assert row.live is False
    svc.repo.save_deployment.assert_called_once_with(row)
    assert any("superseded" in (entry.get("message") or "").lower() for entry in row.logs)


# ---- run_github_deploy -------------------------------------------------------


@pytest.mark.unit
def test_run_github_deploy_noop_when_row_missing():
    svc = _service()
    svc.repo.get_deployment.return_value = None
    svc.run_github_deploy(uuid4())
    svc.repo.get_current_deployment.assert_not_called()


@pytest.mark.unit
def test_run_github_deploy_skips_fetch_when_already_superseded(monkeypatch):
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    row = _deployment(site_id=site_id, workspace_id=workspace_id, version=1)
    newer = _deployment(site_id=site_id, workspace_id=workspace_id, version=2)
    svc.repo.get_deployment.return_value = row
    svc.repo.get_current_deployment.return_value = newer

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(side_effect=AssertionError("should not fetch")))

    svc.run_github_deploy(row.id)

    assert row.status == "completed"
    assert row.is_current is False
    svc.repo.get_site.assert_not_called()


@pytest.mark.unit
def test_run_github_deploy_fails_cleanly_when_connection_missing():
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    row = _deployment(site_id=site_id, workspace_id=workspace_id, version=1)
    svc.repo.get_deployment.return_value = row
    svc.repo.get_current_deployment.return_value = row
    svc.repo.get_site.return_value = _site(workspace_id, site_id)
    svc.repo.get_github_connection.return_value = None

    svc.run_github_deploy(row.id)

    assert row.status == "failed"
    assert "not" in row.error.lower() or "github" in row.error.lower()


@pytest.mark.unit
def test_run_github_deploy_pins_exact_commit_sha_when_fetching_archive(monkeypatch, tmp_path):
    """The archive fetch must use the deployment row's OWN pinned commit
    sha, never the connection's selected_branch or "latest" — proves commit
    pinning survives into the actual fetch call, not just the DB row."""
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    row = _deployment(
        site_id=site_id, workspace_id=workspace_id, version=2,
        source_provider="github", github_commit_sha=COMMIT_SHA, github_branch="main",
    )
    svc.repo.get_deployment.return_value = row
    svc.repo.get_current_deployment.return_value = row
    svc.repo.get_site.return_value = site
    svc.repo.get_github_connection.return_value = connection
    svc.repo.find_previous_completed.return_value = None

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value="ghs_token"))
    fetch_mock = AsyncMock(return_value=123)
    monkeypatch.setattr(github_client, "fetch_repository_archive", fetch_mock)

    pipeline_calls = {}

    def _fake_pipeline(**kw):
        pipeline_calls.update(kw)

    monkeypatch.setattr(svc, "_run_pipeline", _fake_pipeline)
    monkeypatch.setattr("app.static_sites.service.static_site_root", lambda: tmp_path)

    svc.run_github_deploy(row.id)

    fetch_mock.assert_awaited_once()
    called_args = fetch_mock.await_args
    # positional: (token, owner, repo, commit_sha)
    assert called_args.args[1] == connection.repository_owner
    assert called_args.args[2] == connection.repository_name
    assert called_args.args[3] == COMMIT_SHA
    assert called_args.args[3] != connection.selected_branch

    assert pipeline_calls["user"] is None
    assert pipeline_calls["source_type"] == "zip"
    assert pipeline_calls["row"] is row
    assert pipeline_calls["mode"] == "free_subdomain"


@pytest.mark.unit
def test_run_github_deploy_carries_forward_custom_domain_mode(monkeypatch, tmp_path):
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    row = _deployment(
        site_id=site_id, workspace_id=workspace_id, version=2,
        source_provider="github", github_commit_sha=COMMIT_SHA, github_branch="main",
    )
    previous = _deployment(site_id=site_id, workspace_id=workspace_id, version=1, domain="app.example.com")
    svc.repo.get_deployment.return_value = row
    svc.repo.get_current_deployment.return_value = row
    svc.repo.get_site.return_value = site
    svc.repo.get_github_connection.return_value = connection
    svc.repo.find_previous_completed.return_value = previous

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value="ghs_token"))
    monkeypatch.setattr(github_client, "fetch_repository_archive", AsyncMock(return_value=123))
    pipeline_calls = {}
    monkeypatch.setattr(svc, "_run_pipeline", lambda **kw: pipeline_calls.update(kw))
    monkeypatch.setattr("app.static_sites.service.static_site_root", lambda: tmp_path)

    svc.run_github_deploy(row.id)

    assert pipeline_calls["mode"] == "custom"
    assert pipeline_calls["custom_domain"] == "app.example.com"


@pytest.mark.unit
def test_run_github_deploy_archive_fetch_failure_fails_row_and_never_runs_pipeline(monkeypatch, tmp_path):
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    row = _deployment(
        site_id=site_id, workspace_id=workspace_id, version=2,
        source_provider="github", github_commit_sha=COMMIT_SHA, github_branch="main",
    )
    svc.repo.get_deployment.return_value = row
    svc.repo.get_current_deployment.return_value = row
    svc.repo.get_site.return_value = site
    svc.repo.get_github_connection.return_value = connection
    svc.repo.find_previous_completed.return_value = None

    monkeypatch.setattr(
        github_client, "mint_installation_token",
        AsyncMock(side_effect=github_client.GitHubApiError(status_code=503, detail="GitHub is temporarily unavailable.")),
    )
    monkeypatch.setattr("app.static_sites.service.static_site_root", lambda: tmp_path)

    pipeline_called = {"yes": False}
    monkeypatch.setattr(svc, "_run_pipeline", lambda **kw: pipeline_called.__setitem__("yes", True))

    svc.run_github_deploy(row.id)

    assert row.status == "failed"
    assert pipeline_called["yes"] is False


@pytest.mark.unit
def test_run_github_deploy_cleans_up_temp_archive_after_pipeline_runs(monkeypatch, tmp_path):
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    row = _deployment(
        site_id=site_id, workspace_id=workspace_id, version=2,
        source_provider="github", github_commit_sha=COMMIT_SHA, github_branch="main",
    )
    svc.repo.get_deployment.return_value = row
    svc.repo.get_current_deployment.return_value = row
    svc.repo.get_site.return_value = site
    svc.repo.get_github_connection.return_value = connection
    svc.repo.find_previous_completed.return_value = None
    monkeypatch.setattr("app.static_sites.service.static_site_root", lambda: tmp_path)

    async def _write_archive(token, owner, repo, sha, *, dest_path, max_bytes=None):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"PK\x03\x04fake-zip-bytes")
        return len(b"PK\x03\x04fake-zip-bytes")

    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value="ghs_token"))
    monkeypatch.setattr(github_client, "fetch_repository_archive", _write_archive)

    seen_path = {}

    def _fake_pipeline(**kw):
        seen_path["path"] = kw["upload_path"]
        assert kw["upload_path"].exists()

    monkeypatch.setattr(svc, "_run_pipeline", _fake_pipeline)

    svc.run_github_deploy(row.id)

    assert not seen_path["path"].exists(), "the fetched archive must be cleaned up after the pipeline runs"
