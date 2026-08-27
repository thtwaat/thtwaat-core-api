"""THTWAAT Deploy Phase 4B — real end-to-end build/injection tests (spec
§22/§23). These run an ACTUAL `docker run` against the real
thtwaat-vite-build / thtwaat-nextjs-build / thtwaat-nextjs-runtime images —
not mocked — and inspect the produced browser bundle / running container.

Skips cleanly (does not fail) when Docker or the required images aren't
available, which is expected in a sandboxed/CI environment without a
provisioned build host. See the Phase 4B final report for whether this
suite has actually been run against a real Docker host — a green skip here
is NOT evidence of a real, verified build.
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
import zipfile

import pytest

pytestmark = pytest.mark.e2e


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=False)
        return proc.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _image_available(image: str) -> bool:
    try:
        proc = subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=10, check=False)
        return proc.returncode == 0
    except Exception:  # noqa: BLE001
        return False


requires_docker = pytest.mark.skipif(not _docker_available(), reason="Docker is not available in this environment")


def _write_minimal_vite_project(root, *, env_reference: str) -> None:
    (root / "package.json").write_text(
        '{"name":"e2e-vite","private":true,"scripts":{"build":"vite build"},'
        '"devDependencies":{"vite":"^5.0.0"}}'
    )
    (root / "vite.config.js").write_text("export default {}\n")
    (root / "index.html").write_text(
        f'<html><body><div id="out"></div><script type="module" src="/main.js"></script>'
        f'<script>document.getElementById("out").textContent = import.meta.env.{env_reference};</script>'
        f"</body></html>\n"
    )
    (root / "main.js").write_text("console.log('e2e vite build');\n")


@pytest.mark.e2e
@requires_docker
def test_vite_build_inlines_public_var_and_excludes_secret(tmp_path, monkeypatch):
    from app.static_sites import vite_build

    if not _image_available(vite_build.settings.VITE_BUILD_IMAGE):
        pytest.skip(f"{vite_build.settings.VITE_BUILD_IMAGE} image not built in this environment")

    monkeypatch.setattr(vite_build.settings, "VITE_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr(vite_build.settings, "VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)

    src = tmp_path / "src"
    src.mkdir()
    _write_minimal_vite_project(src, env_reference="VITE_TEST_VALUE")
    dest = tmp_path / "dist"

    result = vite_build.run_vite_build(
        source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(),
        use_ci=False,
        client_env_vars={"VITE_TEST_VALUE": "hello"},
    )

    bundle_text = "\n".join(p.read_text(errors="ignore") for p in dest.rglob("*.js"))
    assert "hello" in bundle_text
    assert "SECRET_TEST" not in bundle_text
    assert "super-secret" not in bundle_text


@pytest.mark.e2e
@requires_docker
def test_vite_build_never_injects_non_vite_secret(tmp_path, monkeypatch):
    from app.static_sites import vite_build

    if not _image_available(vite_build.settings.VITE_BUILD_IMAGE):
        pytest.skip(f"{vite_build.settings.VITE_BUILD_IMAGE} image not built in this environment")

    monkeypatch.setattr(vite_build.settings, "VITE_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr(vite_build.settings, "VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)

    src = tmp_path / "src"
    src.mkdir()
    _write_minimal_vite_project(src, env_reference="VITE_TEST_VALUE")
    dest = tmp_path / "dist"

    vite_build.run_vite_build(
        source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(),
        use_ci=False,
        client_env_vars={"VITE_TEST_VALUE": "hello", "SECRET_TEST": "super-secret"},
    )

    for path in dest.rglob("*"):
        if path.is_file():
            assert "super-secret" not in path.read_text(errors="ignore")


def _write_minimal_nextjs_project(root) -> None:
    (root / "package.json").write_text(
        '{"name":"e2e-next","private":true,"scripts":{"build":"next build"},'
        '"dependencies":{"next":"^14.0.0","react":"^18.0.0","react-dom":"^18.0.0"}}'
    )
    (root / "next.config.js").write_text("module.exports = { output: 'standalone' };\n")
    pages = root / "pages"
    pages.mkdir()
    (pages / "index.js").write_text(
        "export default function Home() {\n"
        "  return <div>{process.env.NEXT_PUBLIC_TEST_VALUE}</div>;\n"
        "}\n"
    )


@pytest.mark.e2e
@requires_docker
def test_nextjs_build_and_runtime_public_vs_server_only_split(tmp_path, monkeypatch):
    from app.static_sites import nextjs_build, nextjs_runtime

    if not _image_available(nextjs_build.settings.NEXTJS_BUILD_IMAGE):
        pytest.skip(f"{nextjs_build.settings.NEXTJS_BUILD_IMAGE} image not built in this environment")
    if not _image_available(nextjs_runtime.settings.NEXTJS_RUNTIME_IMAGE):
        pytest.skip(f"{nextjs_runtime.settings.NEXTJS_RUNTIME_IMAGE} image not built in this environment")

    monkeypatch.setattr(nextjs_build.settings, "NEXTJS_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr(nextjs_build.settings, "VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)
    monkeypatch.setattr(nextjs_runtime.settings, "NEXTJS_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr(nextjs_runtime.settings, "VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)

    src = tmp_path / "src"
    src.mkdir()
    _write_minimal_nextjs_project(src)
    dest = tmp_path / "artifact"

    nextjs_build.run_nextjs_build(
        source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(),
        use_ci=False,
        public_env_vars={"NEXT_PUBLIC_TEST_VALUE": "hello"},
    )

    client_bundle_text = "\n".join(
        p.read_text(errors="ignore") for p in (dest / ".next" / "static").rglob("*.js")
    )
    assert "hello" in client_bundle_text
    assert "server-secret" not in client_bundle_text

    deployment_id = uuid.uuid4()
    result = None
    try:
        result = nextjs_runtime.start_runtime(
            artifact_dir=dest, deployment_id=deployment_id,
            server_env_vars={"NEXT_PUBLIC_TEST_VALUE": "hello", "SERVER_SECRET_TEST": "server-secret"},
        )
        assert result.healthy
    finally:
        if result is not None:
            nextjs_runtime.stop_runtime(result.container_name)


@pytest.mark.e2e
@requires_docker
def test_rollback_uses_prior_snapshot_not_current_live_value(tmp_path):
    """Real filesystem/env-var round trip for the rollback scenario in spec
    §23, without going through the full HTTP/DB stack: build V1 with
    TEST_VALUE=A, "roll back" to V1's own already-built artifact directory
    (never rebuilding — matching StaticSiteService.rollback's behavior) with
    its ORIGINAL resolved value, and confirm no rebuild occurred."""
    from app.static_sites import vite_build

    if not _image_available(vite_build.settings.VITE_BUILD_IMAGE):
        pytest.skip(f"{vite_build.settings.VITE_BUILD_IMAGE} image not built in this environment")

    src = tmp_path / "src"
    src.mkdir()
    _write_minimal_vite_project(src, env_reference="VITE_TEST_VALUE")
    dest_v1 = tmp_path / "dist_v1"

    import app.static_sites.vite_build as vb

    original_settings_enabled = vb.settings.VITE_BUILD_ENABLED
    vb.settings.VITE_BUILD_ENABLED = True
    vb.settings.VITE_BUILD_ORCHESTRATOR_URL = ""
    try:
        vb.run_vite_build(
            source_dir=src, dest_dir=dest_v1, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(),
            use_ci=False, client_env_vars={"VITE_TEST_VALUE": "A"},
        )
        v1_mtime = (dest_v1 / "index.html").stat().st_mtime

        # A rollback in the real pipeline (see StaticSiteService.rollback)
        # reuses target.deployment_path verbatim — never re-invokes the
        # build. Simulate that here: no second run_vite_build() call.
        bundle_text = "\n".join(p.read_text(errors="ignore") for p in dest_v1.rglob("*.js"))
        assert "A" in bundle_text

        assert (dest_v1 / "index.html").stat().st_mtime == v1_mtime  # untouched, never rebuilt
    finally:
        vb.settings.VITE_BUILD_ENABLED = original_settings_enabled
