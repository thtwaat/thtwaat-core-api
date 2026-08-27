"""Unit tests for app/static_sites/nextjs_build.py — the Next.js docker run
orchestrator. Mirrors tests/unit/static_sites/test_vite_build.py exactly in
spirit — no real Docker daemon here, subprocess.run is mocked throughout.
"""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.static_sites.nextjs_build import NextjsBuildError, STANDALONE_REQUIRED_MESSAGE, run_nextjs_build


def _enable(monkeypatch, **overrides):
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_BUILD_IMAGE", "thtwaat-nextjs-build:20", raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_BUILD_NETWORK", "thtwaat_vite_build_net", raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_MAX_BUILD_TIME_SECONDS", 600, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_MAX_BUILD_MEMORY_MB", 2048, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_MAX_BUILD_CPU", 1.5, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_BUILD_TMPFS_MB", 512, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_MAX_NODE_MODULES_BYTES", 1536 * 1024 * 1024, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_MAX_OUTPUT_BYTES", 300 * 1024 * 1024, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_MAX_OUTPUT_FILE_COUNT", 40000, raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.NEXTJS_MAX_LOG_BYTES", 200_000, raising=False)
    for k, v in overrides.items():
        monkeypatch.setattr(f"app.static_sites.nextjs_build.settings.{k}", v, raising=False)


def _write_standalone(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "server.js").write_text("require('http').createServer().listen(process.env.PORT)\n")
    (dest / ".next").mkdir(exist_ok=True)
    (dest / ".next" / "static").mkdir(exist_ok=True)
    (dest / ".next" / "static" / "chunk.js").write_text("x")


@pytest.mark.unit
def test_build_disabled_by_default_raises_clear_error(tmp_path):
    with patch("app.static_sites.nextjs_build.settings") as s:
        s.NEXTJS_BUILD_ENABLED = False
        with pytest.raises(NextjsBuildError, match="not enabled"):
            run_nextjs_build(
                source_dir=tmp_path, dest_dir=tmp_path / "out", deployment_id=uuid.uuid4(),
                workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True,
            )


@pytest.mark.unit
def test_successful_build_argv_has_no_docker_socket_no_shell(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        _write_standalone(dest)
        return MagicMock(returncode=0, stdout="build ok", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = run_nextjs_build(
        source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True,
    )

    argv = captured["argv"]
    assert argv[:2] == ["docker", "run"]
    assert "/var/run/docker.sock" not in " ".join(argv)
    assert "--cap-drop" in argv and "ALL" in argv
    assert "--security-opt" in argv and "no-new-privileges" in argv
    assert "--user" in argv and "1000:1000" in argv
    assert "--network" in argv and "thtwaat_vite_build_net" in argv
    assert "--memory" in argv
    assert "--pids-limit" in argv
    assert "--rm" in argv
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    assert any(m.endswith(":/workspace/source:ro") for m in mounts)
    assert any(m.endswith(":/workspace/output:rw") for m in mounts)
    assert len(mounts) == 2
    assert not captured["kwargs"].get("shell", False)
    assert result.file_count == 2


@pytest.mark.unit
def test_no_secret_env_vars_ever_passed(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        _write_standalone(dest)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=False)

    env_flags = [captured["argv"][i + 1] for i, a in enumerate(captured["argv"]) if a == "-e"]
    env_keys = {e.split("=", 1)[0] for e in env_flags}
    assert env_keys == {
        "INSTALL_CMD", "NODE_ENV", "CI", "NPM_CONFIG_FUND", "NPM_CONFIG_AUDIT", "MAX_NODE_MODULES_BYTES",
    }


@pytest.mark.unit
def test_build_timeout_kills_container_and_raises_clean_error(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    killed = {"argv": None}

    def _fake_run(argv, **kwargs):
        if argv[:2] in (["docker", "kill"], ["docker", "rm"]):
            killed["argv"] = argv
            return MagicMock(returncode=0)
        raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError, match="exceeded the allowed resource limit"):
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    assert killed["argv"] is not None


@pytest.mark.unit
def test_docker_unavailable_raises_clean_error(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        raise FileNotFoundError("docker: not found")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError, match="not available"):
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_missing_standalone_output_raises_required_message(tmp_path, monkeypatch):
    """Phase 3's hard requirement: missing .next/standalone must FAIL with
    the exact required message, never silently fall back to static export."""
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)  # "succeeds" but produces nothing
        return MagicMock(returncode=1, stdout=f"Error: {STANDALONE_REQUIRED_MESSAGE}", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError, match="standalone output is required"):
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_missing_server_js_after_zero_exit_still_rejected(tmp_path, monkeypatch):
    """Defense in depth: even if the build container somehow exits 0 without
    producing server.js, the host-side validation must still catch it."""
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError, match="standalone output is required"):
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_forbidden_output_files_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        _write_standalone(dest)
        (dest / ".git").mkdir()
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError, match="unexpected files"):
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_node_modules_in_output_is_allowed(tmp_path, monkeypatch):
    """Unlike Vite's dist/, a Next.js standalone artifact IS supposed to
    contain a pruned node_modules — must not be flagged as forbidden."""
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        _write_standalone(dest)
        (dest / "node_modules").mkdir()
        (dest / "node_modules" / "pkg.js").write_text("x")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)
    assert result.file_count >= 2


@pytest.mark.unit
def test_oversized_output_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch, NEXTJS_MAX_OUTPUT_BYTES=10)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        _write_standalone(dest)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError, match="size limit"):
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_excessive_output_file_count_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch, NEXTJS_MAX_OUTPUT_FILE_COUNT=3)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        _write_standalone(dest)
        for i in range(10):
            (dest / f"f{i}.js").write_text("x")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError, match="file count"):
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_log_output_is_sanitized(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        return MagicMock(returncode=1, stdout="AUTHORIZATION: Bearer sk-supersecrettoken123\nBuild failed\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(NextjsBuildError) as exc:
        run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    joined = "\n".join(exc.value.log_lines)
    assert "sk-supersecrettoken123" not in joined


@pytest.mark.unit
def test_subprocess_env_never_inherits_host_secrets(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()
    monkeypatch.setenv("DB_PASSWORD", "super-secret-db-password")

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["env"] = kwargs.get("env")
        _write_standalone(dest)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_nextjs_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    assert captured["env"] is not None
    assert "DB_PASSWORD" not in captured["env"]
