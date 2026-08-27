"""Integration tests: detection + build orchestration wired into
prepare_deployment() and the deploy service — Phase 18's "run a tiny Vite
project through the deployment pipeline" check. run_vite_build() itself is
mocked (no Docker daemon in this environment); everything else (safe
extraction, flattening, detection, staging cleanup, StaticSiteProvider
hand-off) is real.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.static_sites.provider import StaticDeployError, prepare_deployment
from app.static_sites.vite_build import BuildResult


@pytest.fixture(autouse=True)
def _isolate_static_site_root(tmp_path, monkeypatch):
    """Every test in this module either calls prepare_deployment() directly
    or via the service — both end up calling staging_directory(), which
    resolves through static_site_root(). Never let that touch the real
    project's data/static-sites/, even transiently for the staging dir."""
    monkeypatch.setattr("app.static_sites.provider.static_site_root", lambda: tmp_path / "static-sites-root")


def _make_vite_zip(path: Path, *, with_lockfile: bool = True) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("package.json", json.dumps({
            "name": "tiny-vite-app",
            "scripts": {"build": "vite build", "dev": "vite"},
            "devDependencies": {"vite": "^5.0.0"},
        }))
        zf.writestr("vite.config.js", "export default {}\n")
        zf.writestr("index.html", "<html><body><div id='app'></div></body></html>")
        zf.writestr("src/main.js", "document.getElementById('app').textContent = 'hi';\n")
        if with_lockfile:
            zf.writestr("package-lock.json", "{}")
    return path


@pytest.mark.unit
def test_vite_zip_routes_to_run_vite_build_with_correct_args(tmp_path, monkeypatch):
    zpath = _make_vite_zip(tmp_path / "app.zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    deployment_id = uuid4()

    captured = {}

    def _fake_run_vite_build(*, source_dir, dest_dir, deployment_id, workspace_id, site_id, use_ci, client_env_vars=None):
        captured["source_dir"] = source_dir
        captured["dest_dir"] = dest_dir
        captured["use_ci"] = use_ci
        (dest_dir / "index.html").write_text("<html>built</html>")
        (dest_dir / "assets").mkdir()
        (dest_dir / "assets" / "app.js").write_text("console.log(1)")
        return BuildResult(dist_dir=dest_dir, file_count=2, total_bytes=30, log_lines=["build ok"], duration_ms=1200)

    monkeypatch.setattr("app.static_sites.provider.run_vite_build", _fake_run_vite_build)

    stages_seen = []
    info = prepare_deployment(
        upload_path=zpath, source_type="zip", dest_dir=dest, deployment_id=deployment_id,
        workspace_id=uuid4(), site_id=uuid4(),
        stage_callback=lambda stage, msg: stages_seen.append(stage),
    )

    assert info["framework"] == "vite"
    assert info["file_count"] == 2
    assert info["build_log"] == ["build ok"]
    assert captured["use_ci"] is True  # lockfile present
    assert captured["dest_dir"] == dest
    assert "detecting" in stages_seen
    assert "building" in stages_seen
    assert "validating_output" in stages_seen
    # Source given to the build was extracted somewhere OTHER than dest_dir
    # (a staging dir) — raw package.json/src never end up in the published tree.
    assert captured["source_dir"] != dest
    assert not (dest / "package.json").exists()
    assert not (dest / "src").exists()
    assert (dest / "index.html").read_text() == "<html>built</html>"


@pytest.mark.unit
def test_vite_zip_without_lockfile_uses_install_not_ci(tmp_path, monkeypatch):
    zpath = _make_vite_zip(tmp_path / "app.zip", with_lockfile=False)
    dest = tmp_path / "dest"
    dest.mkdir()

    captured = {}

    def _fake_run_vite_build(*, source_dir, dest_dir, deployment_id, workspace_id, site_id, use_ci, client_env_vars=None):
        captured["use_ci"] = use_ci
        (dest_dir / "index.html").write_text("hi")
        return BuildResult(dist_dir=dest_dir, file_count=1, total_bytes=2, log_lines=[], duration_ms=1)

    monkeypatch.setattr("app.static_sites.provider.run_vite_build", _fake_run_vite_build)

    info = prepare_deployment(
        upload_path=zpath, source_type="zip", dest_dir=dest, deployment_id=uuid4(),
        workspace_id=uuid4(), site_id=uuid4(),
    )

    assert captured["use_ci"] is False
    assert any("npm install" in w for w in info["warnings"])


@pytest.mark.unit
def test_staging_directory_is_always_cleaned_up_on_success(tmp_path, monkeypatch):
    from app.static_sites.provider import staging_directory

    zpath = _make_vite_zip(tmp_path / "app.zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    deployment_id = uuid4()

    def _fake_run_vite_build(*, source_dir, dest_dir, deployment_id, workspace_id, site_id, use_ci, client_env_vars=None):
        (dest_dir / "index.html").write_text("hi")
        return BuildResult(dist_dir=dest_dir, file_count=1, total_bytes=2, log_lines=[], duration_ms=1)

    monkeypatch.setattr("app.static_sites.provider.run_vite_build", _fake_run_vite_build)
    monkeypatch.setattr("app.static_sites.provider.static_site_root", lambda: tmp_path)

    prepare_deployment(
        upload_path=zpath, source_type="zip", dest_dir=dest, deployment_id=deployment_id,
        workspace_id=uuid4(), site_id=uuid4(),
    )

    assert not staging_directory(deployment_id).exists()


@pytest.mark.unit
def test_staging_directory_is_cleaned_up_even_on_build_failure(tmp_path, monkeypatch):
    from app.static_sites.provider import staging_directory
    from app.static_sites.vite_build import BuildError

    zpath = _make_vite_zip(tmp_path / "app.zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    deployment_id = uuid4()

    def _fake_run_vite_build(*, source_dir, dest_dir, deployment_id, workspace_id, site_id, use_ci, client_env_vars=None):
        raise BuildError("Build failed. See logs for details.", log_lines=["npm ERR!"])

    monkeypatch.setattr("app.static_sites.provider.run_vite_build", _fake_run_vite_build)
    monkeypatch.setattr("app.static_sites.provider.static_site_root", lambda: tmp_path)

    with pytest.raises(StaticDeployError) as exc:
        prepare_deployment(
            upload_path=zpath, source_type="zip", dest_dir=dest, deployment_id=deployment_id,
            workspace_id=uuid4(), site_id=uuid4(),
        )

    assert exc.value.log_lines == ["npm ERR!"]
    assert not staging_directory(deployment_id).exists()


def _make_nextjs_zip(path: Path, *, with_lockfile: bool = True) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("package.json", json.dumps({
            "name": "my-next-app",
            "scripts": {"build": "next build", "dev": "next dev"},
            "dependencies": {"next": "14.0.0", "react": "18.2.0", "react-dom": "18.2.0"},
        }))
        zf.writestr("next.config.js", "module.exports = { output: 'standalone' }\n")
        zf.writestr("app/page.tsx", "export default function Page() { return null }\n")
        if with_lockfile:
            zf.writestr("package-lock.json", "{}")
    return path


@pytest.mark.unit
def test_nextjs_zip_routes_to_run_nextjs_build_not_vite(tmp_path, monkeypatch):
    """THTWAAT Phase 3: Next.js is no longer rejected — it must route to
    run_nextjs_build(), never run_vite_build()."""
    zpath = _make_nextjs_zip(tmp_path / "nextapp.zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    deployment_id = uuid4()

    def _fake_run_vite_build(**kw):
        raise AssertionError("run_vite_build must never be called for a Next.js project")

    captured = {}

    def _fake_run_nextjs_build(*, source_dir, dest_dir, deployment_id, workspace_id, site_id, use_ci, public_env_vars=None):
        captured["source_dir"] = source_dir
        captured["dest_dir"] = dest_dir
        captured["use_ci"] = use_ci
        (dest_dir / "server.js").write_text("require('http')\n")
        (dest_dir / ".next").mkdir()
        (dest_dir / ".next" / "static").mkdir()
        from app.static_sites.nextjs_build import NextjsBuildResult
        return NextjsBuildResult(artifact_dir=dest_dir, file_count=2, total_bytes=40, log_lines=["build ok"], duration_ms=3000)

    monkeypatch.setattr("app.static_sites.provider.run_vite_build", _fake_run_vite_build)
    monkeypatch.setattr("app.static_sites.provider.run_nextjs_build", _fake_run_nextjs_build)

    stages_seen = []
    info = prepare_deployment(
        upload_path=zpath, source_type="zip", dest_dir=dest, deployment_id=deployment_id,
        workspace_id=uuid4(), site_id=uuid4(),
        stage_callback=lambda stage, msg: stages_seen.append(stage),
    )

    assert info["framework"] == "nextjs"
    assert info["file_count"] == 2
    assert info["build_log"] == ["build ok"]
    assert captured["use_ci"] is True
    assert captured["source_dir"] != dest
    assert not (dest / "package.json").exists()
    assert (dest / "server.js").is_file()
    assert "building" in stages_seen
    assert "validating_output" in stages_seen


@pytest.mark.unit
def test_nextjs_build_error_surfaces_standalone_required_message(tmp_path, monkeypatch):
    zpath = _make_nextjs_zip(tmp_path / "nextapp.zip")
    dest = tmp_path / "dest"
    dest.mkdir()

    from app.static_sites.nextjs_build import NextjsBuildError, STANDALONE_REQUIRED_MESSAGE

    def _fake_run_nextjs_build(**kw):
        raise NextjsBuildError(STANDALONE_REQUIRED_MESSAGE, log_lines=["next build finished without output: standalone"])

    monkeypatch.setattr("app.static_sites.provider.run_nextjs_build", _fake_run_nextjs_build)

    with pytest.raises(StaticDeployError, match="standalone output is required"):
        prepare_deployment(
            upload_path=zpath, source_type="zip", dest_dir=dest, deployment_id=uuid4(),
            workspace_id=uuid4(), site_id=uuid4(),
        )


@pytest.mark.unit
def test_plain_static_zip_unaffected_by_vite_integration(tmp_path):
    """Regression: a zip with no package.json must take the exact same path
    as before this phase — no detection/build machinery invoked at all."""
    zpath = tmp_path / "site.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("index.html", "<html>plain site</html>")
        zf.writestr("style.css", "body{}")
    dest = tmp_path / "dest"
    dest.mkdir()

    info = prepare_deployment(
        upload_path=zpath, source_type="zip", dest_dir=dest, deployment_id=uuid4(),
        workspace_id=uuid4(), site_id=uuid4(),
    )

    assert info["framework"] == "static_zip"
    assert (dest / "index.html").read_text() == "<html>plain site</html>"
    assert (dest / "style.css").is_file()


@pytest.mark.unit
def test_html_upload_unaffected_by_vite_integration(tmp_path):
    upload = tmp_path / "index.html"
    upload.write_text("<html>hi</html>")
    dest = tmp_path / "dest"

    info = prepare_deployment(
        upload_path=upload, source_type="html", dest_dir=dest, deployment_id=uuid4(),
        workspace_id=uuid4(), site_id=uuid4(),
    )

    assert info["framework"] == "static_html"
    assert (dest / "index.html").read_text() == "<html>hi</html>"


# ---- full service-layer pipeline with a real tiny Vite project (Phase 18) ----


@pytest.mark.unit
def test_full_pipeline_tiny_vite_project_reaches_static_site_provider(tmp_path, monkeypatch):
    """source (real zip bytes) -> detect Vite -> sandbox build (mocked
    docker) -> dist -> StaticSiteProvider (bind_hostname_and_ssl, real
    function, its own domain/ssl calls mocked) -> *.thtwaat.com -> HTTPS ->
    LIVE. Proves the whole chain wires together end to end at the Python
    level; the actual `docker run` and DNS/Let's Encrypt calls are mocked
    since neither Docker nor a public DNS zone is available here."""
    import app.apps.model  # noqa: F401 — mapper registration, see test_service.py
    import app.companies.model  # noqa: F401
    import app.users.model  # noqa: F401
    import app.auth.model  # noqa: F401
    import app.storage.model  # noqa: F401
    import app.domains.models  # noqa: F401
    import app.static_sites.models  # noqa: F401
    from app.static_sites.models import StaticSite
    from app.static_sites.service import StaticSiteService

    # Isolate deployment_directory()'s real filesystem writes to tmp_path —
    # never the actual project's data/static-sites/.
    monkeypatch.setattr("app.static_sites.provider.static_site_root", lambda: tmp_path / "static-sites")

    svc = StaticSiteService(MagicMock())
    svc.repo = MagicMock()
    site = StaticSite(id=uuid4(), workspace_id=uuid4(), name="Tiny Vite App", slug="tiny-vite-app")

    def _stamp(row):
        for field, default in (
            ("id", uuid4), ("instructions", list), ("logs", list), ("urls", dict), ("health", dict),
            ("ssl", dict), ("duration_ms", int), ("retryable", lambda: False), ("file_count", int),
            ("total_bytes", int), ("upload_size_bytes", int), ("is_current", lambda: True),
            ("live", lambda: False), ("environment", lambda: "production"), ("provider", lambda: "static"),
            ("status", lambda: "queued"), ("stage", lambda: "queued"),
            ("created_at", lambda: datetime.now(timezone.utc)), ("updated_at", lambda: datetime.now(timezone.utc)),
        ):
            if getattr(row, field, None) is None:
                setattr(row, field, default())
        return row

    svc.repo.get_site_for_workspace.return_value = site
    svc.repo.next_deployment_version.return_value = 1
    svc.repo.create_deployment.side_effect = _stamp
    svc.repo.save_deployment.side_effect = _stamp

    zpath = _make_vite_zip(tmp_path / "tiny.zip")

    def _fake_run_vite_build(*, source_dir, dest_dir, deployment_id, workspace_id, site_id, use_ci, client_env_vars=None):
        # Prove real project files (package.json, vite.config.js, src/) were
        # actually extracted and handed to the "build" as source.
        assert (source_dir / "package.json").is_file()
        assert (source_dir / "vite.config.js").is_file()
        assert (source_dir / "src" / "main.js").is_file()
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "index.html").write_text("<html>tiny vite app — built</html>")
        (dest_dir / "assets").mkdir()
        (dest_dir / "assets" / "index.js").write_text("console.log('hi')")
        return BuildResult(
            dist_dir=dest_dir, file_count=2, total_bytes=60,
            log_lines=["Installing dependencies (npm ci)...", "vite v5 building for production...", "✓ built in 40ms"],
            duration_ms=800,
        )

    monkeypatch.setattr("app.static_sites.provider.run_vite_build", _fake_run_vite_build)
    monkeypatch.setattr(
        "app.static_sites.service.bind_hostname_and_ssl",
        lambda *a, **kw: {"ssl_status": "ACTIVE", "domain_id": str(uuid4())},
    )
    monkeypatch.setattr(
        "app.studio.domain_validation.resolve_deploy_hostname",
        lambda **kw: ("tiny-vite-app-abc123.thtwaat.com", "free_subdomain", SimpleNamespace(reachable=True)),
    )
    monkeypatch.setattr("app.studio.deploy.probe_http", lambda url, **kw: {"ok": True, "status_code": 200})

    result = svc.deploy_upload(
        SimpleNamespace(id=str(uuid4()), email="owner@example.com", role="admin", company_id=str(site.workspace_id)),
        site.id,
        upload_path=zpath,
        source_type="zip",
        original_filename="tiny.zip",
        upload_size_bytes=zpath.stat().st_size,
    )

    assert result.framework == "vite"
    assert result.status == "completed"
    assert result.live is True
    assert result.urls["website"] == "https://tiny-vite-app-abc123.thtwaat.com"
    assert result.file_count == 2
    assert any("vite" in line.lower() for entry in [result] for line in [str(result.logs)])
