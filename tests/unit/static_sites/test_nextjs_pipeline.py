"""Service-level tests for THTWAAT Phase 3 (Next.js): zero-downtime deploy,
rollback without rebuild, per-company runtime limits. Mirrors
tests/unit/static_sites/test_service.py's MagicMock(db)/MagicMock(repo)
harness — no real database or Docker required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.apps.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401
import app.storage.model  # noqa: F401
import app.users.model  # noqa: F401
from app.static_sites import nextjs_runtime
from app.static_sites.models import StaticSite, StaticSiteDeployment
from app.static_sites.schemas import StaticSiteRollbackRequest
from app.static_sites.service import StaticSiteService


@pytest.fixture(autouse=True)
def _no_real_redis(monkeypatch):
    """_emit() best-effort-publishes SSE progress via
    app.studio.deploy_events.publish_deploy_event(), which opens a real
    Redis connection (REDIS_HOST from .env, typically the compose service
    name "redis") — unreachable and slow to fail (DNS) outside a container.
    Unit tests must never depend on that; stub it out like any other
    external service call."""
    monkeypatch.setattr("app.studio.deploy_events.publish_deploy_event", lambda *a, **kw: None)


def _profile(role: str, *, company_id=None, user_id=None):
    return SimpleNamespace(
        id=str(user_id or uuid4()), email="user@example.com", role=role, company_id=str(company_id or uuid4()),
    )


def _stamp_db_defaults(row):
    defaults = {
        "id": lambda: uuid4(),
        "instructions": lambda: [], "logs": lambda: [], "urls": lambda: {}, "health": lambda: {}, "ssl": lambda: {},
        "duration_ms": lambda: 0, "retryable": lambda: False, "file_count": lambda: 0, "total_bytes": lambda: 0,
        "upload_size_bytes": lambda: 0, "is_current": lambda: True, "live": lambda: False,
        "environment": lambda: "production", "provider": lambda: "static", "status": lambda: "queued",
        "stage": lambda: "queued", "created_at": lambda: datetime.now(timezone.utc),
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
    svc.repo.count_live_nextjs_runtimes.return_value = 0
    # THTWAAT Deploy Phase 6A — production's runtime cap now also counts
    # live PREVIEW runtimes (see StaticSiteService._run_pipeline); default
    # to zero here so these production-only tests are unaffected.
    svc.repo.count_live_preview_nextjs_runtimes.return_value = 0
    svc.repo.find_previous_completed.return_value = None
    return svc


def _base_site(workspace_id=None) -> StaticSite:
    return StaticSite(id=uuid4(), workspace_id=workspace_id or uuid4(), name="Demo", slug="demo")


def _wire_domain_and_health(monkeypatch, *, ok: bool = True):
    """Mirrors test_service.py's convention: mock bind_hostname_and_ssl()
    wholesale (like test_deploy_upload_html_success_marks_live does) rather
    than its internals — bind_free_subdomain()/bind_domain_and_ssl() do real
    DNS/Studio work this test harness has no business exercising. Returns
    the captured kwargs dict of the last call so callers can assert on
    whether runtime_target or deployment_dir was passed."""
    captured = {}

    def _fake_bind(*args, **kwargs):
        captured.clear()
        captured.update(kwargs)
        return {"ssl_status": "ACTIVE" if ok else "PENDING", "domain_id": str(uuid4())}

    monkeypatch.setattr("app.static_sites.service.bind_hostname_and_ssl", _fake_bind)
    monkeypatch.setattr("app.studio.deploy.probe_http", lambda url, **kw: {"ok": ok, "status_code": 200 if ok else 503})
    return captured


def _wire_rollback_ssl(monkeypatch, *, runtime_ok: bool = True):
    """Rollback() calls DomainService/SslManager directly (not through
    bind_hostname_and_ssl) — mock those two, matching
    test_rollback_v1_then_v2_then_rollback_restores_v1's convention."""
    fake_domain = SimpleNamespace(id=uuid4())
    fake_domain_service = MagicMock()
    fake_domain_service.repo.get_by_hostname.return_value = fake_domain
    fake_ssl_manager = MagicMock()
    fake_ssl_manager.set_runtime_proxy_target.return_value = {"ssl_status": "ACTIVE" if runtime_ok else "PENDING"}
    fake_ssl_manager.set_static_root.return_value = {"ssl_status": "ACTIVE" if runtime_ok else "PENDING"}
    monkeypatch.setattr("app.domains.service.DomainService", lambda db: fake_domain_service)
    monkeypatch.setattr("app.ssl.manager.SslManager", lambda db: fake_ssl_manager)
    monkeypatch.setattr("app.studio.deploy.probe_http", lambda url, **kw: {"ok": runtime_ok, "status_code": 200})
    return fake_ssl_manager


@pytest.mark.unit
def test_nextjs_deploy_starts_runtime_and_binds_runtime_target_not_static_root(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1

    monkeypatch.setattr(
        "app.static_sites.service.prepare_deployment",
        lambda **kw: {"file_count": 5, "total_bytes": 999, "framework": "nextjs", "warnings": [], "build_log": []},
    )
    monkeypatch.setattr(
        "app.studio.domain_validation.resolve_deploy_hostname",
        lambda **kw: ("demo-abc123.thtwaat.com", "free_subdomain", SimpleNamespace(reachable=True)),
    )

    started = {}

    def _fake_start_runtime(*, artifact_dir, deployment_id, server_env_vars=None):
        started["deployment_id"] = deployment_id
        name = nextjs_runtime.container_name(deployment_id)
        return nextjs_runtime.RuntimeStartResult(container_name=name, healthy=True, status_code=200, log_lines=["ok"])

    monkeypatch.setattr("app.static_sites.nextjs_runtime.start_runtime", _fake_start_runtime)
    _wire_domain_and_health(monkeypatch, ok=True)

    upload = tmp_path / "app.zip"
    upload.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="zip", original_filename="app.zip",
        upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "completed"
    assert result.live is True
    assert result.runtime_type == "node"
    assert result.runtime_container_id == nextjs_runtime.container_name(started["deployment_id"])


@pytest.mark.unit
def test_nextjs_deploy_calls_set_runtime_proxy_target(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1

    monkeypatch.setattr(
        "app.static_sites.service.prepare_deployment",
        lambda **kw: {"file_count": 5, "total_bytes": 999, "framework": "nextjs", "warnings": [], "build_log": []},
    )
    monkeypatch.setattr(
        "app.studio.domain_validation.resolve_deploy_hostname",
        lambda **kw: ("demo-abc123.thtwaat.com", "free_subdomain", SimpleNamespace(reachable=True)),
    )
    monkeypatch.setattr(
        "app.static_sites.nextjs_runtime.start_runtime",
        lambda *, artifact_dir, deployment_id, server_env_vars=None: nextjs_runtime.RuntimeStartResult(
            container_name=nextjs_runtime.container_name(deployment_id), healthy=True, status_code=200,
        ),
    )
    captured = _wire_domain_and_health(monkeypatch, ok=True)

    upload = tmp_path / "app.zip"
    upload.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="zip", original_filename="app.zip",
        upload_size_bytes=upload.stat().st_size,
    )

    # A Next.js deploy must call bind_hostname_and_ssl with runtime_target
    # set and deployment_dir=None — the seam that makes it use
    # SslManager.set_runtime_proxy_target() instead of set_static_root()
    # (see provider.py::bind_hostname_and_ssl).
    assert captured.get("runtime_target")
    assert captured.get("deployment_dir") is None


@pytest.mark.unit
def test_nextjs_v2_health_check_failure_keeps_v1_live(tmp_path, monkeypatch):
    """Phase 11/21: a failed v2 (runtime never becomes healthy) must leave
    v1 marked is_current=True and must never touch nginx/domain state."""
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 2

    v1 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1, is_current=True,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id="thtwaat-nextjs-runtime-" + uuid4().hex,
        deployment_path=str(tmp_path / "v1"), subdomain="demo.thtwaat.com", live=True,
    )
    svc.repo.find_previous_completed.return_value = v1

    monkeypatch.setattr(
        "app.static_sites.service.prepare_deployment",
        lambda **kw: {"file_count": 5, "total_bytes": 999, "framework": "nextjs", "warnings": [], "build_log": []},
    )

    def _fake_start_runtime(*, artifact_dir, deployment_id, server_env_vars=None):
        raise nextjs_runtime.RuntimeError_("Runtime container failed its health check within the startup timeout.")

    monkeypatch.setattr("app.static_sites.nextjs_runtime.start_runtime", _fake_start_runtime)
    stop_calls = []
    monkeypatch.setattr("app.static_sites.nextjs_runtime.stop_runtime", lambda name: stop_calls.append(name))

    upload = tmp_path / "app.zip"
    upload.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="zip", original_filename="app.zip",
        upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "failed"
    assert "health check" in result.error.lower()
    # v1 restored as current — _fail() does this via find_previous_completed
    saved_rows = [c.args[0] for c in svc.repo.save_deployment.call_args_list]
    assert any(r is v1 and r.is_current is True for r in saved_rows)
    # v1's own (still-healthy) runtime must never have been stopped — only
    # the failed v2 attempt (which never had a container to stop, since
    # start_runtime raised before returning one) could appear in stop_calls.
    assert v1.runtime_container_id not in stop_calls


@pytest.mark.unit
def test_nextjs_company_runtime_limit_blocks_deploy_without_starting_runtime(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    svc.repo.count_live_nextjs_runtimes.return_value = 10
    monkeypatch.setattr("app.static_sites.service.settings.NEXTJS_MAX_RUNTIMES_PER_COMPANY", 10, raising=False)

    monkeypatch.setattr(
        "app.static_sites.service.prepare_deployment",
        lambda **kw: {"file_count": 5, "total_bytes": 999, "framework": "nextjs", "warnings": [], "build_log": []},
    )
    called = {"start": False}

    def _fake_start_runtime(**kw):
        called["start"] = True
        raise AssertionError("must never start a runtime once the per-company limit is reached")

    monkeypatch.setattr("app.static_sites.nextjs_runtime.start_runtime", _fake_start_runtime)

    upload = tmp_path / "app.zip"
    upload.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="zip", original_filename="app.zip",
        upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "failed"
    assert "limit" in result.error.lower()
    assert called["start"] is False


@pytest.mark.unit
def test_nextjs_zero_downtime_stops_previous_runtime_only_after_cutover(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 2

    v1_container = "thtwaat-nextjs-runtime-" + uuid4().hex
    v1 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1, is_current=False,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id=v1_container,
        deployment_path=str(tmp_path / "v1"), subdomain="demo.thtwaat.com", live=True,
    )
    svc.repo.find_previous_completed.return_value = v1

    monkeypatch.setattr(
        "app.static_sites.service.prepare_deployment",
        lambda **kw: {"file_count": 5, "total_bytes": 999, "framework": "nextjs", "warnings": [], "build_log": []},
    )
    monkeypatch.setattr(
        "app.studio.domain_validation.resolve_deploy_hostname",
        lambda **kw: ("demo.thtwaat.com", "free_subdomain", SimpleNamespace(reachable=True)),
    )
    monkeypatch.setattr(
        "app.static_sites.nextjs_runtime.start_runtime",
        lambda *, artifact_dir, deployment_id, server_env_vars=None: nextjs_runtime.RuntimeStartResult(
            container_name=nextjs_runtime.container_name(deployment_id), healthy=True, status_code=200,
        ),
    )
    stop_calls = []
    monkeypatch.setattr("app.static_sites.nextjs_runtime.stop_runtime", lambda name: stop_calls.append(name))
    _wire_domain_and_health(monkeypatch, ok=True)

    upload = tmp_path / "app.zip"
    upload.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    result = svc.deploy_upload(
        _profile("admin", company_id=site.workspace_id), site.id,
        upload_path=upload, source_type="zip", original_filename="app.zip",
        upload_size_bytes=upload.stat().st_size,
    )

    assert result.status == "completed"
    assert stop_calls == [v1_container]


# ---- rollback (Phase 12) ----------------------------------------------------


@pytest.mark.unit
def test_nextjs_rollback_reuses_running_container_never_rebuilds(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    v2_container = "thtwaat-nextjs-runtime-" + uuid4().hex
    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    v1 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1, is_current=False,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id=v2_container,
        deployment_path=str(v1_dir), subdomain="demo.thtwaat.com", live=True,
        file_count=1, total_bytes=1,
    )
    v2 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=2, is_current=True,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id="thtwaat-nextjs-runtime-" + uuid4().hex,
        deployment_path=str(tmp_path / "v2"), subdomain="demo.thtwaat.com", live=True,
        file_count=1, total_bytes=1,
    )
    svc.repo.get_current_deployment.return_value = v2
    svc.repo.find_previous_completed.return_value = v1
    svc.repo.next_deployment_version.return_value = 3

    monkeypatch.setattr("app.static_sites.nextjs_runtime.is_running", lambda name: name == v1.runtime_container_id)

    def _fail_start(**kw):
        raise AssertionError("must reuse the running container, never start a new one or rebuild")

    monkeypatch.setattr("app.static_sites.nextjs_runtime.start_runtime", _fail_start)

    def _fail_build(**kw):
        raise AssertionError("rollback must never rebuild")

    monkeypatch.setattr("app.static_sites.provider.run_nextjs_build", _fail_build)

    stop_calls = []
    monkeypatch.setattr("app.static_sites.nextjs_runtime.stop_runtime", lambda name: stop_calls.append(name))
    _wire_rollback_ssl(monkeypatch, runtime_ok=True)

    result = svc.rollback(_profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())

    created_row = svc.repo.create_deployment.call_args[0][0]
    assert created_row.runtime_container_id == v1.runtime_container_id
    assert created_row.deployment_path == str(v1_dir)
    assert result.status == "completed"
    # v2 (rolled back FROM) must be stopped after cutover.
    assert v2.runtime_container_id in stop_calls


@pytest.mark.unit
def test_nextjs_rollback_starts_fresh_container_from_old_artifact_when_not_running(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    old_container = "thtwaat-nextjs-runtime-" + uuid4().hex
    v1 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1, is_current=False,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id=old_container,  # long stopped/removed
        deployment_path=str(v1_dir), subdomain="demo.thtwaat.com", live=True,
        file_count=1, total_bytes=1,
    )
    v2 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=2, is_current=True,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id="thtwaat-nextjs-runtime-" + uuid4().hex,
        deployment_path=str(tmp_path / "v2"), subdomain="demo.thtwaat.com", live=True,
        file_count=1, total_bytes=1,
    )
    svc.repo.get_current_deployment.return_value = v2
    svc.repo.find_previous_completed.return_value = v1
    svc.repo.next_deployment_version.return_value = 3

    monkeypatch.setattr("app.static_sites.nextjs_runtime.is_running", lambda name: False)

    started = {}

    def _fake_start_runtime(*, artifact_dir, deployment_id, server_env_vars=None):
        started["artifact_dir"] = artifact_dir
        started["deployment_id"] = deployment_id
        return nextjs_runtime.RuntimeStartResult(
            container_name=nextjs_runtime.container_name(deployment_id), healthy=True, status_code=200,
        )

    monkeypatch.setattr("app.static_sites.nextjs_runtime.start_runtime", _fake_start_runtime)

    def _fail_build(**kw):
        raise AssertionError("rollback must never rebuild")

    monkeypatch.setattr("app.static_sites.provider.run_nextjs_build", _fail_build)
    _wire_rollback_ssl(monkeypatch, runtime_ok=True)

    result = svc.rollback(_profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())

    assert str(started["artifact_dir"]) == str(v1_dir), "must build the runtime from v1's immutable artifact directory"
    assert started["deployment_id"] != v1.id, "the new container is owned by the NEW rollback row, not the old one"
    assert result.status == "completed"
    assert result.runtime_container_id == nextjs_runtime.container_name(started["deployment_id"])


@pytest.mark.unit
def test_nextjs_rollback_health_failure_keeps_previous_live(tmp_path, monkeypatch):
    svc = _service()
    site = _base_site()
    svc.repo.get_site_for_workspace.return_value = site

    v1_dir = tmp_path / "v1"
    v1_dir.mkdir()
    v1 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=1, is_current=False,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id="thtwaat-nextjs-runtime-" + uuid4().hex,
        deployment_path=str(v1_dir), subdomain="demo.thtwaat.com", live=True, file_count=1, total_bytes=1,
    )
    v2 = StaticSiteDeployment(
        id=uuid4(), site_id=site.id, workspace_id=site.workspace_id, version=2, is_current=True,
        status="completed", stage="completed", source_type="zip", framework="nextjs",
        runtime_type="node", runtime_container_id="thtwaat-nextjs-runtime-" + uuid4().hex,
        deployment_path=str(tmp_path / "v2"), subdomain="demo.thtwaat.com", live=True, file_count=1, total_bytes=1,
    )
    svc.repo.get_current_deployment.return_value = v2
    svc.repo.find_previous_completed.return_value = v1
    svc.repo.next_deployment_version.return_value = 3

    monkeypatch.setattr("app.static_sites.nextjs_runtime.is_running", lambda name: False)

    def _fake_start_runtime(*, artifact_dir, deployment_id, server_env_vars=None):
        raise nextjs_runtime.RuntimeError_("Runtime container failed its health check within the startup timeout.")

    monkeypatch.setattr("app.static_sites.nextjs_runtime.start_runtime", _fake_start_runtime)

    result = svc.rollback(_profile("admin", company_id=site.workspace_id), site.id, StaticSiteRollbackRequest())

    assert result.status == "failed"
    assert "health check" in result.error.lower()
