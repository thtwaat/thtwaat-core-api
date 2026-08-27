"""Integration-style unit tests for THTWAAT Deploy Phase 4B's wiring into
StaticSiteService's deploy/rollback pipeline (service.py) — snapshotting,
per-environment isolation, fail-closed resolution, secret redaction, and
rollback-uses-snapshot-not-live-config. Mirrors test_service.py's
MagicMock(db)/MagicMock(repo) style; the repo mock is backed by a tiny
in-memory store so snapshot_env_vars()/resolve_deployment_env_vars() (the
REAL functions, not mocked) exercise realistic read/write round trips."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.users.model  # noqa: F401
import app.apps.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.storage.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401

from app.static_sites.env_crypto import encrypt_value
from app.static_sites.models import StaticSite, StaticSiteDeployment, StaticSiteDeploymentEnvVar, StaticSiteEnvironmentVariable
from app.static_sites.schemas import StaticSiteRollbackRequest
from app.static_sites.service import StaticSiteService

SECRET_PLAINTEXT = "SUPER_SECRET_123456"


def _profile(role: str = "admin", *, company_id=None, user_id=None):
    return SimpleNamespace(id=str(user_id or uuid4()), email="user@example.com", role=role, company_id=str(company_id or uuid4()))


def _base_site(workspace_id=None) -> StaticSite:
    return StaticSite(id=uuid4(), workspace_id=workspace_id or uuid4(), name="Demo", slug="demo")


def _stamp_db_defaults(row):
    defaults = {
        "id": lambda: uuid4(),
        "instructions": lambda: [], "logs": lambda: [], "urls": lambda: {}, "health": lambda: {}, "ssl": lambda: {},
        "duration_ms": lambda: 0, "retryable": lambda: False, "file_count": lambda: 0, "total_bytes": lambda: 0,
        "upload_size_bytes": lambda: 0, "is_current": lambda: True, "live": lambda: False,
        "environment": lambda: "production", "provider": lambda: "static", "status": lambda: "queued",
        "stage": lambda: "queued", "created_at": lambda: datetime.now(timezone.utc), "updated_at": lambda: datetime.now(timezone.utc),
    }
    for field, factory in defaults.items():
        if getattr(row, field, None) is None:
            setattr(row, field, factory())
    return row


class _FakeEnvVarStore:
    """Minimal in-memory backing for the two tables env_resolver.py touches
    — lets the REAL snapshot_env_vars()/resolve_deployment_env_vars()/
    clone_env_var_snapshot() run against a MagicMock(repo) without a real DB."""

    def __init__(self):
        self.live: list[StaticSiteEnvironmentVariable] = []
        self.snapshots: list[StaticSiteDeploymentEnvVar] = []

    def list_env_vars(self, site_id, workspace_id, environment=None):
        return [
            r for r in self.live
            if r.site_id == site_id and r.workspace_id == workspace_id and (environment is None or r.environment == environment)
        ]

    def create_deployment_env_var_snapshot(self, rows):
        for r in rows:
            if getattr(r, "id", None) is None:
                r.id = uuid4()
        self.snapshots.extend(rows)
        return rows

    def list_deployment_env_var_snapshot(self, deployment_id):
        return [r for r in self.snapshots if r.deployment_id == deployment_id]

    def add_live(self, key, value, *, site_id, workspace_id, environment="production", is_secret=True):
        row = StaticSiteEnvironmentVariable(
            id=uuid4(), workspace_id=workspace_id, site_id=site_id, key=key,
            encrypted_value=encrypt_value(value), environment=environment, is_secret=is_secret,
        )
        self.live.append(row)
        return row


def _service_with_env_store():
    svc = StaticSiteService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.create_deployment.side_effect = _stamp_db_defaults
    svc.repo.save_deployment.side_effect = _stamp_db_defaults
    store = _FakeEnvVarStore()
    svc.repo.list_env_vars.side_effect = store.list_env_vars
    svc.repo.create_deployment_env_var_snapshot.side_effect = store.create_deployment_env_var_snapshot
    svc.repo.list_deployment_env_var_snapshot.side_effect = store.list_deployment_env_var_snapshot
    return svc, store


def _mock_happy_path_pipeline(monkeypatch, *, framework="static_html", build_log=None, capture_resolved=None):
    def _fake_prepare(**kw):
        if capture_resolved is not None:
            capture_resolved.append(kw.get("resolved_env_vars"))
        return {"file_count": 1, "total_bytes": 10, "framework": framework, "warnings": [], "build_log": build_log or []}

    monkeypatch.setattr("app.static_sites.service.prepare_deployment", _fake_prepare)
    monkeypatch.setattr(
        "app.studio.domain_validation.resolve_deploy_hostname",
        lambda **kw: ("demo-abc123.thtwaat.com", "free_subdomain", SimpleNamespace(reachable=True)),
    )
    monkeypatch.setattr(
        "app.static_sites.service.bind_hostname_and_ssl",
        lambda *a, **kw: {"ssl_status": "ACTIVE", "domain_id": str(uuid4())},
    )
    monkeypatch.setattr("app.studio.deploy.probe_http", lambda url, **kw: {"ok": True, "status_code": 200})


# ---- snapshot creation --------------------------------------------------------


@pytest.mark.unit
def test_deploy_creates_immutable_env_var_snapshot(tmp_path, monkeypatch):
    svc, store = _service_with_env_store()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    store.add_live("DATABASE_URL", "postgres://prod-db", site_id=site.id, workspace_id=site.workspace_id)

    captured = []
    _mock_happy_path_pipeline(monkeypatch, capture_resolved=captured)

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")
    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html", upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "completed"
    snapshot_rows = store.list_deployment_env_var_snapshot(result.id)
    assert len(snapshot_rows) == 1
    assert snapshot_rows[0].key == "DATABASE_URL"
    resolved = captured[0]
    assert resolved[0].key == "DATABASE_URL"
    assert resolved[0].value == "postgres://prod-db"


@pytest.mark.unit
def test_a_later_live_edit_never_changes_an_already_snapshotted_deployment(tmp_path, monkeypatch):
    """Phase 4B spec §17 concurrency scenario: deployment V1 starts (snapshot
    taken), then the live var is updated — V1's snapshot must be unaffected."""
    svc, store = _service_with_env_store()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    live_row = store.add_live("DATABASE_URL", "A", site_id=site.id, workspace_id=site.workspace_id)

    _mock_happy_path_pipeline(monkeypatch)
    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")
    v1 = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html", upload_size_bytes=upload.stat().st_size,
    )

    # Simulate a user editing the live env var AFTER v1's snapshot was taken.
    live_row.encrypted_value = encrypt_value("B")

    v1_snapshot = store.list_deployment_env_var_snapshot(v1.id)
    from app.static_sites.env_crypto import decrypt_value

    assert decrypt_value(v1_snapshot[0].encrypted_value) == "A"

    svc.repo.next_deployment_version.return_value = 2
    upload2 = tmp_path / "index2.html"
    upload2.write_text("<html>hi v2</html>")
    v2 = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload2, source_type="html", original_filename="index.html", upload_size_bytes=upload2.stat().st_size,
    )
    v2_snapshot = store.list_deployment_env_var_snapshot(v2.id)
    assert decrypt_value(v2_snapshot[0].encrypted_value) == "B"


# ---- environment isolation -----------------------------------------------------


@pytest.mark.unit
def test_production_deployment_never_resolves_development_vars(tmp_path, monkeypatch):
    svc, store = _service_with_env_store()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    store.add_live("SHARED_KEY", "prod-value", site_id=site.id, workspace_id=site.workspace_id, environment="production")
    store.add_live("DEV_ONLY_KEY", "dev-value", site_id=site.id, workspace_id=site.workspace_id, environment="development")

    captured = []
    _mock_happy_path_pipeline(monkeypatch, capture_resolved=captured)
    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")
    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html", upload_size_bytes=upload.stat().st_size,
        environment="production",
    )

    assert result.status == "completed"
    keys = {r.key for r in captured[0]}
    assert keys == {"SHARED_KEY"}
    assert "DEV_ONLY_KEY" not in keys


# ---- fail-closed resolution -----------------------------------------------------


@pytest.mark.unit
def test_undecryptable_env_var_fails_deployment_before_any_build(tmp_path, monkeypatch):
    svc, store = _service_with_env_store()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    bad_row = StaticSiteEnvironmentVariable(
        id=uuid4(), workspace_id=site.workspace_id, site_id=site.id, key="BROKEN",
        encrypted_value="not-a-real-fernet-token", environment="production", is_secret=True,
    )
    store.live.append(bad_row)

    prepare_called = MagicMock()
    monkeypatch.setattr("app.static_sites.service.prepare_deployment", prepare_called)

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")
    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html", upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "failed"
    assert "BROKEN" in (result.error or "")
    prepare_called.assert_not_called()


# ---- secret redaction integration ------------------------------------------------


@pytest.mark.unit
def test_secret_value_leaking_into_build_log_is_redacted_before_storage(tmp_path, monkeypatch):
    svc, store = _service_with_env_store()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    store.add_live("OPENAI_API_KEY", SECRET_PLAINTEXT, site_id=site.id, workspace_id=site.workspace_id, is_secret=True)

    # Simulate a build tool accidentally echoing the secret to its own stdout.
    _mock_happy_path_pipeline(monkeypatch, build_log=[f"Using key {SECRET_PLAINTEXT}", "unrelated line"])

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")
    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html", upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "completed"
    all_messages = " ".join(entry.get("message", "") for entry in result.logs)
    assert SECRET_PLAINTEXT not in all_messages
    assert "[REDACTED]" in all_messages


# ---- rollback uses snapshot, not live config --------------------------------------


@pytest.mark.unit
def test_rollback_restores_target_snapshot_not_current_live_env(tmp_path, monkeypatch):
    svc, store = _service_with_env_store()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    live_row = store.add_live("DATABASE_URL", "A", site_id=site.id, workspace_id=site.workspace_id)

    _mock_happy_path_pipeline(monkeypatch)
    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")
    v1 = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="html", original_filename="index.html", upload_size_bytes=upload.stat().st_size,
    )
    v1_row = StaticSiteDeployment(
        id=v1.id, site_id=site.id, workspace_id=site.workspace_id, version=1, is_current=True, status="completed",
        stage="completed", source_type="html", framework="static_html", deployment_path=str(tmp_path),
        environment="production", live=True, created_at=v1.created_at, updated_at=v1.updated_at,
    )

    # Live config changes AFTER v1 — a naive rollback re-resolving live vars
    # would pick this up; the snapshot-based rollback must not.
    live_row.encrypted_value = encrypt_value("B")

    svc.repo.get_current_deployment.return_value = v1_row
    svc.repo.get_deployment.return_value = v1_row
    svc.repo.next_deployment_version.return_value = 2
    svc.repo.find_previous_completed.return_value = None

    monkeypatch.setattr("app.studio.deploy.probe_http", lambda url, **kw: {"ok": True, "status_code": 200})

    rolled_back = svc.rollback(
        _profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest(deployment_id=v1.id)
    )

    assert rolled_back.status == "completed"
    from app.static_sites.env_crypto import decrypt_value

    rollback_snapshot = store.list_deployment_env_var_snapshot(rolled_back.id)
    assert len(rollback_snapshot) == 1
    assert decrypt_value(rollback_snapshot[0].encrypted_value) == "A"
