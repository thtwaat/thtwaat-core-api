"""Unit tests for PreviewDeploymentService (THTWAAT Deploy Phase 6A) —
create_or_advance() (webhook fast path), run_preview_deploy() (worker
entrypoint, stale-build guard), and teardown(). Mirrors
test_github_deploy_service.py's MagicMock(repo) style; GitHub network calls
mocked via AsyncMock, quota checks mocked via UsageService patch."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
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
from app.static_sites.github_webhook import PullRequestEvent
from app.static_sites.models import GitHubConnection, StaticSite, StaticSitePreviewDeployment
from app.static_sites.preview_service import PreviewDeploymentService

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


def _stamp(row):
    defaults = {
        "id": lambda: uuid4(), "logs": lambda: [], "urls": lambda: {},
        "generation": lambda: 1, "status": lambda: "queued", "stage": lambda: "queued",
        "created_at": lambda: datetime.now(timezone.utc), "updated_at": lambda: datetime.now(timezone.utc),
    }
    for field, factory in defaults.items():
        if getattr(row, field, None) is None:
            setattr(row, field, factory())
    return row


def _service() -> PreviewDeploymentService:
    svc = PreviewDeploymentService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.create_preview.side_effect = _stamp
    svc.repo.save_preview.side_effect = _stamp
    # run_preview_deploy() snapshots/resolves preview env vars BEFORE
    # fetching the archive — every test that reaches that far needs these
    # to behave like "no preview-tagged env vars configured" by default.
    svc.repo.list_env_vars.return_value = []
    svc.repo.create_preview_env_var_snapshot.side_effect = lambda rows: rows
    svc.repo.list_preview_env_var_snapshot.return_value = []
    return svc


def _site(workspace_id=None, site_id=None) -> StaticSite:
    return StaticSite(id=site_id or uuid4(), workspace_id=workspace_id or uuid4(), name="Demo", slug="demo")


def _connection(*, workspace_id, site_id) -> GitHubConnection:
    return GitHubConnection(
        id=uuid4(), workspace_id=workspace_id, site_id=site_id,
        installation_id="42", github_account_id="1", github_username="octocat", account_type="User",
        repository_owner="octocat", repository_name="app", repository_id="555",
        default_branch="main", selected_branch="main", created_by=None,
    )


def _pr_event(**overrides) -> PullRequestEvent:
    base = dict(
        action="opened", repository_id="555", repository_owner="octocat", repository_name="app",
        installation_id="42", pr_number=7, head_sha=COMMIT_A, head_ref="feature-x", base_ref="main",
        head_repository_id="555", is_fork=False, sender_login="octocat",
    )
    base.update(overrides)
    return PullRequestEvent(**base)


def _preview(*, site_id, workspace_id, pr_number=7, **overrides) -> StaticSitePreviewDeployment:
    base = dict(
        id=uuid4(), site_id=site_id, workspace_id=workspace_id, pr_number=pr_number,
        branch="feature-x", base_branch="main", commit_sha=COMMIT_A, generation=1,
        status="ready", stage="completed", hostname=f"pr-{pr_number}-demo-abcd1234.thtwaat.com",
        urls={}, logs=[], torn_down_at=None,
    )
    base.update(overrides)
    return _stamp(StaticSitePreviewDeployment(**base))


def _no_quota_breach():
    return patch("app.usage.service.UsageService.check_quota", return_value=True)


# ---- create_or_advance -------------------------------------------------------


@pytest.mark.unit
def test_create_or_advance_opened_creates_new_row_with_quota_check():
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    svc.repo.get_preview_by_pr.return_value = None
    svc.repo.count_active_previews_for_company.return_value = 0

    with _no_quota_breach() as mock_check:
        row = svc.create_or_advance(site=site, connection=connection, event=_pr_event())

    mock_check.assert_called_once()
    assert mock_check.call_args.kwargs.get("quantity") == 1 or mock_check.call_args[0][-1] == 1
    assert row.pr_number == 7
    assert row.commit_sha == COMMIT_A
    assert row.generation == 1
    assert row.hostname.startswith("pr-7-")
    assert row.github_repository_owner == "octocat"  # from connection, not raw payload


@pytest.mark.unit
def test_create_or_advance_opened_blocked_by_quota_raises_429():
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    svc.repo.get_preview_by_pr.return_value = None
    svc.repo.count_active_previews_for_company.return_value = 1

    with patch(
        "app.usage.service.UsageService.check_quota",
        side_effect=HTTPException(status_code=429, detail={"error": "quota_exceeded"}),
    ):
        with pytest.raises(HTTPException) as exc:
            svc.create_or_advance(site=site, connection=connection, event=_pr_event())
    assert exc.value.status_code == 429
    svc.repo.create_preview.assert_not_called()


@pytest.mark.unit
def test_create_or_advance_synchronize_updates_same_row_no_quota_check():
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    existing = _preview(site_id=site_id, workspace_id=workspace_id, commit_sha=COMMIT_A, generation=1)
    svc.repo.get_preview_by_pr.return_value = existing

    with _no_quota_breach() as mock_check:
        row = svc.create_or_advance(
            site=site, connection=connection, event=_pr_event(action="synchronize", head_sha=COMMIT_B)
        )

    mock_check.assert_not_called()  # synchronize of an already-active preview never re-checks quota
    assert row.id == existing.id
    assert row.commit_sha == COMMIT_B
    assert row.generation == 2
    svc.repo.create_preview.assert_not_called()
    svc.repo.save_preview.assert_called()


@pytest.mark.unit
def test_create_or_advance_reopen_after_teardown_checks_quota_and_resurrects_row():
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    torn_down = _preview(
        site_id=site_id, workspace_id=workspace_id, generation=3,
        torn_down_at=datetime.now(timezone.utc), teardown_reason="pr_closed",
        hostname="pr-7-demo-abcd1234.thtwaat.com",
    )
    svc.repo.get_preview_by_pr.return_value = torn_down
    svc.repo.count_active_previews_for_company.return_value = 0

    with _no_quota_breach() as mock_check:
        row = svc.create_or_advance(site=site, connection=connection, event=_pr_event(action="reopened", head_sha=COMMIT_B))

    mock_check.assert_called_once()
    assert row.id == torn_down.id
    assert row.torn_down_at is None
    assert row.teardown_reason is None
    assert row.generation == 4
    assert row.hostname == "pr-7-demo-abcd1234.thtwaat.com"  # reuses the SAME hostname, not a fresh one


@pytest.mark.unit
def test_create_or_advance_uses_connections_trusted_owner_not_payload():
    svc = _service()
    workspace_id, site_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    connection.repository_owner = "trusted-owner"
    connection.repository_name = "trusted-repo"
    svc.repo.get_preview_by_pr.return_value = None
    svc.repo.count_active_previews_for_company.return_value = 0

    with _no_quota_breach():
        row = svc.create_or_advance(
            site=site, connection=connection,
            event=_pr_event(repository_owner="attacker-controlled", repository_name="evil"),
        )

    assert row.github_repository_owner == "trusted-owner"
    assert row.github_repository_name == "trusted-repo"


# ---- request_close ------------------------------------------------------------


@pytest.mark.unit
def test_request_close_returns_none_when_no_active_preview():
    svc = _service()
    site = _site()
    svc.repo.get_preview_by_pr.return_value = None
    assert svc.request_close(site=site, pr_number=7) is None


@pytest.mark.unit
def test_request_close_returns_none_when_already_torn_down():
    svc = _service()
    site = _site()
    torn_down = _preview(site_id=site.id, workspace_id=site.workspace_id, torn_down_at=datetime.now(timezone.utc))
    svc.repo.get_preview_by_pr.return_value = torn_down
    assert svc.request_close(site=site, pr_number=7) is None


@pytest.mark.unit
def test_request_close_returns_preview_id_for_active_preview():
    svc = _service()
    site = _site()
    active = _preview(site_id=site.id, workspace_id=site.workspace_id)
    svc.repo.get_preview_by_pr.return_value = active
    assert svc.request_close(site=site, pr_number=7) == active.id


# ---- run_preview_deploy: guards ------------------------------------------------


@pytest.mark.unit
def test_run_preview_deploy_noop_when_row_missing():
    svc = _service()
    svc.repo.get_preview.return_value = None
    svc.run_preview_deploy(uuid4(), 1)
    svc.repo.get_site.assert_not_called()


@pytest.mark.unit
def test_run_preview_deploy_noop_when_already_torn_down():
    svc = _service()
    row = _preview(site_id=uuid4(), workspace_id=uuid4(), torn_down_at=datetime.now(timezone.utc))
    svc.repo.get_preview.return_value = row
    svc.run_preview_deploy(row.id, row.generation)
    svc.repo.get_site.assert_not_called()


@pytest.mark.unit
def test_run_preview_deploy_stale_at_start_skips_entirely():
    """Guard #1 — a job enqueued for an OLD generation must never even
    fetch the archive if a newer synchronize already advanced the row."""
    svc = _service()
    row = _preview(site_id=uuid4(), workspace_id=uuid4(), generation=3)
    svc.repo.get_preview.return_value = row
    svc.run_preview_deploy(row.id, 2)  # job pinned to generation 2, row is already at 3
    svc.repo.get_site.assert_not_called()


@pytest.mark.unit
def test_run_preview_deploy_fails_cleanly_when_connection_missing():
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    row = _preview(site_id=site_id, workspace_id=workspace_id, generation=1, status="queued")
    svc.repo.get_preview.return_value = row
    svc.repo.get_site.return_value = _site(workspace_id, site_id)
    svc.repo.get_github_connection.return_value = None

    svc.run_preview_deploy(row.id, 1)

    assert row.status == "failed"
    assert "github" in (row.error or "").lower()


@pytest.mark.unit
def test_run_preview_deploy_archive_fetch_failure_fails_row(monkeypatch, tmp_path):
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    row = _preview(site_id=site_id, workspace_id=workspace_id, generation=1, status="queued")
    svc.repo.get_preview.return_value = row
    svc.repo.get_site.return_value = site
    svc.repo.get_github_connection.return_value = connection
    monkeypatch.setattr("app.static_sites.preview_service.static_site_root", lambda: tmp_path)
    monkeypatch.setattr(
        github_client, "mint_installation_token",
        AsyncMock(side_effect=github_client.GitHubApiError(status_code=503, detail="GitHub is temporarily unavailable.")),
    )

    svc.run_preview_deploy(row.id, 1)

    assert row.status == "failed"


@pytest.mark.unit
def test_run_preview_deploy_stale_before_activation_discards_build(monkeypatch, tmp_path):
    """Guard #2 — a synchronize that lands (via the API server process)
    WHILE this build is running must make the build's output get discarded
    without ever touching the row, once the build itself succeeds."""
    svc = _service()
    site_id, workspace_id = uuid4(), uuid4()
    site = _site(workspace_id, site_id)
    connection = _connection(workspace_id=workspace_id, site_id=site_id)
    row = _preview(site_id=site_id, workspace_id=workspace_id, generation=1, status="queued")
    # By the time the build finishes, the DB row has moved to generation 2
    # (a concurrent synchronize) — simulate via a second, different mock.
    advanced = _preview(site_id=site_id, workspace_id=workspace_id, generation=2, status="queued")
    advanced.id = row.id
    svc.repo.get_preview.side_effect = [row, advanced]
    svc.repo.get_site.return_value = site
    svc.repo.get_github_connection.return_value = connection
    monkeypatch.setattr("app.static_sites.preview_service.static_site_root", lambda: tmp_path)
    monkeypatch.setattr(github_client, "mint_installation_token", AsyncMock(return_value="ghs_token"))

    async def _write_archive(token, owner, repo, sha, *, dest_path, max_bytes=None):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"PK\x03\x04fake")
        return 8

    monkeypatch.setattr(github_client, "fetch_repository_archive", _write_archive)

    def _fake_prepare(**kw):
        dest_dir = kw["dest_dir"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "index.html").write_text("hi")
        return {"file_count": 1, "total_bytes": 2, "framework": "static_zip", "warnings": [], "build_log": []}

    monkeypatch.setattr("app.static_sites.preview_service.prepare_deployment", _fake_prepare)

    svc.run_preview_deploy(row.id, 1)  # job pinned to generation 1

    # Row must never have been mutated to "ready" for a superseded build.
    save_calls = [c.args[0] for c in svc.repo.save_preview.call_args_list]
    assert all(getattr(r, "status", None) != "ready" for r in save_calls)


# ---- teardown -----------------------------------------------------------------


@pytest.mark.unit
def test_teardown_is_idempotent_noop_when_missing():
    svc = _service()
    svc.repo.get_preview.return_value = None
    svc.teardown(uuid4(), reason="pr_closed")
    svc.repo.save_preview.assert_not_called()


@pytest.mark.unit
def test_teardown_is_idempotent_noop_when_already_torn_down():
    svc = _service()
    row = _preview(site_id=uuid4(), workspace_id=uuid4(), torn_down_at=datetime.now(timezone.utc))
    svc.repo.get_preview.return_value = row
    svc.teardown(row.id, reason="expired")
    svc.repo.save_preview.assert_not_called()


@pytest.mark.unit
def test_teardown_marks_row_torn_down_with_reason(monkeypatch):
    svc = _service()
    row = _preview(site_id=uuid4(), workspace_id=uuid4(), deployment_path=None, hostname=None)
    svc.repo.get_preview.return_value = row

    svc.teardown(row.id, reason="pr_closed")

    assert row.status == "torn_down"
    assert row.torn_down_at is not None
    assert row.teardown_reason == "pr_closed"
    assert row.runtime_container_id is None
    assert row.deployment_path is None


@pytest.mark.unit
def test_teardown_stops_runtime_and_removes_vhost(monkeypatch):
    svc = _service()
    container_id = "thtwaat-nextjs-runtime-" + "a" * 32
    row = _preview(
        site_id=uuid4(), workspace_id=uuid4(),
        runtime_container_id=container_id,
        hostname="pr-7-demo-abcd1234.thtwaat.com",
        deployment_path=None,
    )
    svc.repo.get_preview.return_value = row

    stop_mock = MagicMock()
    monkeypatch.setattr("app.static_sites.nextjs_runtime.stop_runtime", stop_mock)
    remove_vhost_mock = MagicMock()
    reload_nginx_mock = MagicMock()
    monkeypatch.setattr("app.ssl.nginx_gen.remove_vhost", remove_vhost_mock)
    monkeypatch.setattr("app.ssl.nginx_gen.reload_nginx", reload_nginx_mock)
    domain_service_mock = MagicMock()
    domain_service_mock.repo.get_by_hostname.return_value = None
    monkeypatch.setattr(
        "app.domains.service.DomainService", MagicMock(return_value=domain_service_mock)
    )

    svc.teardown(row.id, reason="pr_closed")

    stop_mock.assert_called_once_with(container_id)
    remove_vhost_mock.assert_called_once_with("pr-7-demo-abcd1234.thtwaat.com")
    reload_nginx_mock.assert_called_once()
    assert row.runtime_container_id is None


@pytest.mark.unit
def test_teardown_never_deletes_directory_outside_this_preview_id(monkeypatch, tmp_path):
    """Regression guard for the previews/ sibling-directory deletion bug
    caught during implementation: teardown must only ever rmtree a
    directory whose name matches THIS preview's own id."""
    svc = _service()
    preview_id = uuid4()
    other_preview_dir = tmp_path / "previews" / str(uuid4())
    other_preview_dir.mkdir(parents=True)
    (other_preview_dir / "marker.txt").write_text("must survive")

    this_preview_dir = tmp_path / "previews" / str(preview_id)
    (this_preview_dir / "1").mkdir(parents=True)

    row = _preview(
        site_id=uuid4(), workspace_id=uuid4(), hostname=None,
        deployment_path=str(this_preview_dir / "1"),
    )
    row.id = preview_id
    svc.repo.get_preview.return_value = row

    svc.teardown(row.id, reason="pr_closed")

    assert not this_preview_dir.exists()
    assert other_preview_dir.exists()
    assert (other_preview_dir / "marker.txt").exists()


@pytest.mark.unit
def test_teardown_syncs_usage_gauge_downward(monkeypatch):
    svc = _service()
    row = _preview(site_id=uuid4(), workspace_id=uuid4(), hostname=None, deployment_path=None)
    svc.repo.get_preview.return_value = row
    svc.repo.count_active_previews_for_company.return_value = 0

    record_mock = MagicMock()
    monkeypatch.setattr("app.usage.service.UsageService.record", record_mock)

    svc.teardown(row.id, reason="pr_closed")

    record_mock.assert_called_once()
