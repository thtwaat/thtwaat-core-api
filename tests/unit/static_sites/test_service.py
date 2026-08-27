"""Unit tests for app/static_sites/service.py — RBAC, company isolation,
deploy pipeline, and rollback semantics. Mirrors tests/deploy/test_ssl_deploy.py's
MagicMock(db)/MagicMock(repo) style — no real database required."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

# Constructing real StaticSite/StaticSiteDeployment ORM instances triggers
# SQLAlchemy's declarative mapper configuration for the WHOLE shared
# registry (every Base subclass), including string-based relationship()
# targets on unrelated models like Company. Import the same full model set
# alembic/env.py imports so every referenced class name is registered
# before the first real ORM object is constructed, rather than relying on
# import order from unrelated test modules.
import app.users.model  # noqa: F401
import app.apps.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.storage.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401

from app.static_sites.models import StaticSite, StaticSiteDeployment
from app.static_sites.schemas import StaticSiteCreateRequest, StaticSiteRollbackRequest
from app.static_sites.service import StaticSiteService, _GENERIC_FAILURE_MESSAGE


def _profile(role: str, *, company_id=None, user_id=None):
    return SimpleNamespace(
        id=str(user_id or uuid4()),
        email="user@example.com",
        role=role,
        company_id=str(company_id or uuid4()),
    )


def _stamp_db_defaults(row):
    """Mimic what a real commit/refresh would backfill (Column defaults +
    server_default timestamps) — our mocked repo never touches a real DB,
    so plain object construction leaves these None."""
    from datetime import datetime, timezone

    defaults = {
        "id": lambda: uuid4(),
        "instructions": lambda: [],
        "logs": lambda: [],
        "urls": lambda: {},
        "health": lambda: {},
        "ssl": lambda: {},
        "duration_ms": lambda: 0,
        "retryable": lambda: False,
        "file_count": lambda: 0,
        "total_bytes": lambda: 0,
        "upload_size_bytes": lambda: 0,
        "is_current": lambda: True,
        "live": lambda: False,
        "environment": lambda: "production",
        "provider": lambda: "static",
        "status": lambda: "queued",
        "stage": lambda: "queued",
        "created_at": lambda: datetime.now(timezone.utc),
        "updated_at": lambda: datetime.now(timezone.utc),
    }
    for field, factory in defaults.items():
        if getattr(row, field, None) is None:
            setattr(row, field, factory())
    return row


def _service() -> StaticSiteService:
    svc = StaticSiteService(MagicMock())
    svc.repo = MagicMock()
    svc.repo.create_deployment.side_effect = _stamp_db_defaults
    svc.repo.save_deployment.side_effect = _stamp_db_defaults
    return svc


# ---- RBAC ----------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("role", ["employee", "viewer", "manager", "developer"])
def test_non_owner_admin_cannot_deploy(role):
    svc = _service()
    with pytest.raises(HTTPException) as exc:
        svc._require_deploy_manager(_profile(role))
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("role", ["company_owner", "admin", "super_admin"])
def test_owner_admin_super_admin_can_deploy(role):
    svc = _service()
    svc._require_deploy_manager(_profile(role))  # must not raise


# ---- company isolation -----------------------------------------------------


@pytest.mark.unit
def test_get_site_cross_company_returns_404():
    svc = _service()
    svc.repo.get_site_for_workspace.return_value = None
    with pytest.raises(HTTPException) as exc:
        svc._get_site(_profile("admin"), uuid4())
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_get_deployment_cross_site_returns_404():
    svc = _service()
    site = StaticSite(id=uuid4(), workspace_id=uuid4(), name="Site", slug="site")
    svc.repo.get_site_for_workspace.return_value = site

    other_deployment = StaticSiteDeployment(
        id=uuid4(), site_id=uuid4(), workspace_id=site.workspace_id, version=1,
        status="completed", stage="completed", source_type="zip", environment="production",
        live=True, file_count=1, total_bytes=10, duration_ms=0, retryable=False,
    )
    svc.repo.get_deployment.return_value = other_deployment

    with pytest.raises(HTTPException) as exc:
        svc.get_deployment(_profile("admin", company_id=site.workspace_id), site.id, other_deployment.id)
    assert exc.value.status_code == 404


# ---- create_site -----------------------------------------------------------


@pytest.mark.unit
def test_create_site_slugifies_and_dedupes():
    svc = _service()
    svc.repo.get_site_by_slug.side_effect = [object(), None]  # first slug taken, second free
    svc.repo.create_site.side_effect = _stamp_db_defaults

    resp = svc.create_site(_profile("admin"), StaticSiteCreateRequest(name="My Cool Site!"))

    assert resp.slug == "my-cool-site-2"


# ---- deploy pipeline --------------------------------------------------------


def _base_site(workspace_id=None) -> StaticSite:
    return StaticSite(id=uuid4(), workspace_id=workspace_id or uuid4(), name="Demo", slug="demo")


@pytest.mark.unit
def test_deploy_upload_html_success_marks_live(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1

    monkeypatch.setattr(
        "app.static_sites.service.prepare_deployment",
        lambda **kw: {"file_count": 1, "total_bytes": 42, "framework": "static_html", "warnings": [], "build_log": []},
    )
    monkeypatch.setattr(
        "app.studio.domain_validation.resolve_deploy_hostname",
        lambda **kw: ("demo-abc123.thtwaat.com", "free_subdomain", SimpleNamespace(reachable=True)),
    )
    monkeypatch.setattr(
        "app.static_sites.service.bind_hostname_and_ssl",
        lambda *a, **kw: {"ssl_status": "ACTIVE", "domain_id": str(uuid4())},
    )
    monkeypatch.setattr("app.studio.deploy.probe_http", lambda url, **kw: {"ok": True, "status_code": 200})

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id),
        site.id,
        upload_path=upload,
        source_type="html",
        original_filename="index.html",
        upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "completed"
    assert result.live is True
    assert result.urls["website"] == "https://demo-abc123.thtwaat.com"
    assert not upload.exists(), "temp upload must be cleaned up after processing"


@pytest.mark.unit
def test_deploy_upload_missing_index_html_marks_failed(tmp_path, monkeypatch):
    from app.static_sites.provider import StaticDeployError

    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1

    def _raise(**kw):
        raise StaticDeployError("index.html was not found.")

    monkeypatch.setattr("app.static_sites.service.prepare_deployment", _raise)

    upload = tmp_path / "site.zip"
    upload.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # minimal empty-zip-ish bytes

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id),
        site.id,
        upload_path=upload,
        source_type="zip",
        original_filename="site.zip",
        upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "failed"
    assert result.error == "index.html was not found."
    assert result.live is False


@pytest.mark.unit
def test_deploy_upload_unexpected_error_is_sanitized(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1

    def _boom(**kw):
        raise RuntimeError("leaked internal path: C:\\secrets\\prod.env")

    monkeypatch.setattr("app.static_sites.service.prepare_deployment", _boom)

    upload = tmp_path / "site.zip"
    upload.write_bytes(b"junk")

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id),
        site.id,
        upload_path=upload,
        source_type="zip",
        original_filename="site.zip",
        upload_size_bytes=4,
    )

    assert result.status == "failed"
    assert result.error == _GENERIC_FAILURE_MESSAGE
    assert "secrets" not in (result.error or "")
    assert "C:\\" not in (result.error or "")


@pytest.mark.unit
def test_deploy_upload_directory_creation_failure_marks_failed_not_stuck_queued(tmp_path, monkeypatch):
    """Regression: a failure OUTSIDE the extract/hostname-resolve try blocks
    (e.g. the isolated deployment directory itself can't be created) must
    still land the row at status=failed with a sanitized message — not leave
    it stuck at queued/validating with no response reaching the client."""
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1

    def _boom(*a, **kw):
        raise OSError("disk full: /some/internal/mount/path")

    monkeypatch.setattr("app.static_sites.service.deployment_directory", _boom)

    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id),
        site.id,
        upload_path=upload,
        source_type="html",
        original_filename="index.html",
        upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "failed"
    assert result.error == _GENERIC_FAILURE_MESSAGE
    assert "disk full" not in (result.error or "")
    assert "/some/internal/mount/path" not in (result.error or "")


@pytest.mark.unit
def test_deploy_upload_requires_domain_when_custom_mode():
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    with pytest.raises(HTTPException) as exc:
        svc.deploy_upload(
            _profile("admin", company_id=site.workspace_id),
            site.id,
            upload_path=__import__("pathlib").Path("unused.html"),
            source_type="html",
            original_filename="index.html",
            upload_size_bytes=10,
            domain_mode="custom",
            custom_domain=None,
        )
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_non_owner_admin_cannot_call_deploy_upload():
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    with pytest.raises(HTTPException) as exc:
        svc.deploy_upload(
            _profile("employee", company_id=site.workspace_id),
            site.id,
            upload_path=__import__("pathlib").Path("unused.html"),
            source_type="html",
            original_filename="index.html",
            upload_size_bytes=10,
        )
    assert exc.value.status_code == 403


# ---- rollback ---------------------------------------------------------------


@pytest.mark.unit
def test_rollback_v1_then_v2_then_rollback_restores_v1(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    (v1_dir / "index.html").write_text("v1 content")

    v1 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1,
        is_current=False, status="completed", stage="completed", source_type="html",
        deployment_path=str(v1_dir), domain=None, subdomain="demo.thtwaat.com",
        environment="production", live=True, file_count=1, total_bytes=10,
        duration_ms=0, retryable=False, urls={"website": "https://demo.thtwaat.com"},
    )
    v2 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=2,
        is_current=True, status="completed", stage="completed", source_type="html",
        deployment_path=str(tmp_path / "v2"), domain=None, subdomain="demo.thtwaat.com",
        environment="production", live=True, file_count=1, total_bytes=12,
        duration_ms=0, retryable=False,
    )

    svc.repo.get_current_deployment.return_value = v2
    svc.repo.find_previous_completed.return_value = v1
    svc.repo.next_deployment_version.return_value = 3

    fake_domain = SimpleNamespace(id=uuid4())
    fake_domain_service = MagicMock()
    fake_domain_service.repo.get_by_hostname.return_value = fake_domain
    fake_ssl_manager = MagicMock()
    fake_ssl_manager.set_static_root.return_value = {"ssl_status": "ACTIVE"}

    monkeypatch.setattr("app.domains.service.DomainService", lambda db: fake_domain_service)
    monkeypatch.setattr("app.ssl.manager.SslManager", lambda db: fake_ssl_manager)
    monkeypatch.setattr("app.studio.deploy.probe_http", lambda url, **kw: {"ok": True, "status_code": 200})

    result = svc.rollback(_profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())

    # deployment_path is deliberately not exposed on the API response (it's
    # an internal filesystem path) — assert against the persisted row itself.
    created_row = svc.repo.create_deployment.call_args[0][0]
    assert created_row.deployment_path == str(v1_dir), "rollback must reuse v1's directory, never re-extract"

    assert result.rollback_of == v1.id
    assert result.status == "completed"
    assert result.live is True
    fake_ssl_manager.set_static_root.assert_called_once()
    args, _ = fake_ssl_manager.set_static_root.call_args
    assert args[2] == str(v1_dir)


@pytest.mark.unit
def test_rollback_rejects_when_no_previous_completed_deployment():
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.get_current_deployment.return_value = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1,
        status="completed", stage="completed", source_type="html", environment="production",
        live=True, file_count=1, total_bytes=1, duration_ms=0, retryable=False,
    )
    svc.repo.find_previous_completed.return_value = None

    with pytest.raises(HTTPException) as exc:
        svc.rollback(_profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_rollback_rejects_when_target_content_missing_on_disk(tmp_path):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    current = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=2,
        status="completed", stage="completed", source_type="html", environment="production",
        live=True, file_count=1, total_bytes=1, duration_ms=0, retryable=False,
    )
    target = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1,
        status="completed", stage="completed", source_type="html", environment="production",
        live=True, file_count=1, total_bytes=1, duration_ms=0, retryable=False,
        deployment_path=str(tmp_path / "does-not-exist"),
    )
    svc.repo.get_current_deployment.return_value = current
    svc.repo.find_previous_completed.return_value = target

    with pytest.raises(HTTPException) as exc:
        svc.rollback(_profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())
    assert exc.value.status_code == 400


@pytest.mark.unit
def test_rollback_unexpected_failure_marks_failed_not_stuck_queued(tmp_path, monkeypatch):
    """Regression: an unexpected failure after the rollback row is created
    (queued) must still land it at status=failed, never stuck at queued."""
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    (v1_dir / "index.html").write_text("v1 content")

    current = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=2,
        status="completed", stage="completed", source_type="html", environment="production",
        live=True, file_count=1, total_bytes=1, duration_ms=0, retryable=False,
    )
    target = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1,
        status="completed", stage="completed", source_type="html", environment="production",
        live=True, file_count=1, total_bytes=10, duration_ms=0, retryable=False,
        deployment_path=str(v1_dir), subdomain="demo.thtwaat.com",
    )
    svc.repo.get_current_deployment.return_value = current
    svc.repo.find_previous_completed.return_value = target
    svc.repo.next_deployment_version.return_value = 3

    def _boom(*a, **kw):
        raise RuntimeError("unexpected internal failure with a secret token abc123")

    monkeypatch.setattr("app.studio.deploy.probe_http", _boom)
    fake_domain_service = MagicMock()
    fake_domain_service.repo.get_by_hostname.return_value = SimpleNamespace(id=uuid4())
    fake_ssl_manager = MagicMock()
    fake_ssl_manager.set_static_root.return_value = {"ssl_status": "ACTIVE"}
    monkeypatch.setattr("app.domains.service.DomainService", lambda db: fake_domain_service)
    monkeypatch.setattr("app.ssl.manager.SslManager", lambda db: fake_ssl_manager)

    result = svc.rollback(_profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())

    assert result.status == "failed"
    assert result.error == _GENERIC_FAILURE_MESSAGE
    assert "secret token" not in (result.error or "")


@pytest.mark.unit
def test_non_owner_admin_cannot_rollback():
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    with pytest.raises(HTTPException) as exc:
        svc.rollback(_profile("employee", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())
    assert exc.value.status_code == 403
