"""Unit tests for app/static_sites/vite_build.py — the docker run orchestrator.

No real Docker daemon is available in this environment, so subprocess.run is
mocked throughout. What's proven here: the exact argv constructed (no shell,
no user-controlled strings, correct isolation flags), timeout/failure
handling, output validation, and log sanitization/truncation — all the parts
that don't require an actual container runtime to verify.
"""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.static_sites.vite_build import BuildError, run_vite_build


def _enable(monkeypatch, **overrides):
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_BUILD_IMAGE", "thtwaat-vite-build:20", raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_BUILD_NETWORK", "thtwaat_vite_build_net", raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_MAX_BUILD_TIME_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_MAX_BUILD_MEMORY_MB", 1536, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_MAX_BUILD_CPU", 1.0, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_BUILD_TMPFS_MB", 512, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_MAX_NODE_MODULES_BYTES", 1024**3, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_MAX_OUTPUT_BYTES", 100 * 1024 * 1024, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_MAX_OUTPUT_FILE_COUNT", 20000, raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_MAX_LOG_BYTES", 200_000, raising=False)
    for k, v in overrides.items():
        monkeypatch.setattr(f"app.static_sites.vite_build.settings.{k}", v, raising=False)


@pytest.mark.unit
def test_build_disabled_by_default_raises_clear_error(tmp_path):
    with patch("app.static_sites.vite_build.settings") as s:
        s.VITE_BUILD_ENABLED = False
        with pytest.raises(BuildError, match="not enabled"):
            run_vite_build(source_dir=tmp_path, dest_dir=tmp_path / "out", deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


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
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("<html>built</html>")
        return MagicMock(returncode=0, stdout="build ok", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

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
    # source read-only, output read-write, no other bind mounts
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    assert any(m.endswith(":/workspace/source:ro") for m in mounts)
    assert any(m.endswith(":/workspace/output:rw") for m in mounts)
    assert len(mounts) == 2
    # Never pass shell=True
    assert kwargs_shell_absent_or_false(captured["kwargs"])
    assert result.file_count == 1


def kwargs_shell_absent_or_false(kwargs) -> bool:
    return not kwargs.get("shell", False)


@pytest.mark.unit
def test_no_secret_env_vars_ever_passed(tmp_path, monkeypatch):
    """The build container must never receive DB/JWT/SSL/webhook secrets —
    only a small explicit allowlist of build-safe env vars."""
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("hi")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=False)

    env_flags = [captured["argv"][i + 1] for i, a in enumerate(captured["argv"]) if a == "-e"]
    env_keys = {e.split("=", 1)[0] for e in env_flags}
    assert env_keys == {
        "INSTALL_CMD", "NODE_ENV", "CI", "NPM_CONFIG_FUND", "NPM_CONFIG_AUDIT", "MAX_NODE_MODULES_BYTES",
    }
    assert "INSTALL_CMD=install" in env_flags


@pytest.mark.unit
def test_use_ci_true_passes_ci_install_cmd(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()
    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("hi")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    assert "INSTALL_CMD=ci" in captured["argv"]


@pytest.mark.unit
def test_build_timeout_kills_container_and_raises_clean_error(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    killed = {"argv": None}

    def _fake_run(argv, **kwargs):
        if argv[:2] == ["docker", "kill"] or argv[:2] == ["docker", "rm"]:
            killed["argv"] = argv
            return MagicMock(returncode=0)
        raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError, match="exceeded the allowed resource limit"):
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    assert killed["argv"] is not None


@pytest.mark.unit
def test_docker_unavailable_raises_clean_error_not_raw_exception(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        raise FileNotFoundError("docker: not found")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError, match="not available"):
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_nonzero_exit_raises_build_failed_with_logs_attached(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        return MagicMock(returncode=1, stdout="npm ERR! something broke", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError, match="Build failed") as exc:
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    assert any("npm ERR" in line for line in exc.value.log_lines)


@pytest.mark.unit
def test_missing_dist_index_html_raises_clean_error(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)  # build "succeeds" but produces nothing useful
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError, match="index.html was not found"):
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_forbidden_output_files_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("hi")
        (dest / "node_modules").mkdir()
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError, match="unexpected files"):
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_oversized_output_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch, VITE_MAX_OUTPUT_BYTES=10)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("<html>" * 100)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError, match="size limit"):
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_excessive_output_file_count_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch, VITE_MAX_OUTPUT_FILE_COUNT=3)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("hi")
        for i in range(10):
            (dest / f"f{i}.js").write_text("x")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError, match="file count"):
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)


@pytest.mark.unit
def test_log_output_is_sanitized_and_truncated(tmp_path, monkeypatch):
    _enable(monkeypatch, VITE_MAX_LOG_BYTES=50)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    def _fake_run(argv, **kwargs):
        return MagicMock(
            returncode=1,
            stdout="AUTHORIZATION: Bearer sk-supersecrettoken123\n" + ("noisy log line\n" * 50),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(BuildError) as exc:
        run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    joined = "\n".join(exc.value.log_lines)
    assert "sk-supersecrettoken123" not in joined
    assert "AUTHORIZATION=****" in joined or "authorization=****" in joined.lower()
    assert "… (log truncated)" in exc.value.log_lines


@pytest.mark.unit
def test_subprocess_env_never_inherits_host_secrets(tmp_path, monkeypatch):
    """The subprocess.run() call that launches `docker run` must use a
    minimal, explicit env — not silently inherit the calling (api/worker)
    process's full environment, which carries DB_PASSWORD/JWT_SECRET_KEY/
    webhook secrets injected via docker-compose's env_file."""
    _enable(monkeypatch)
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()

    monkeypatch.setenv("DB_PASSWORD", "super-secret-db-password")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-jwt-key")

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["env"] = kwargs.get("env")
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("hi")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_vite_build(source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), use_ci=True)

    env = captured["env"]
    assert env is not None, "subprocess.run must be called with an explicit env=, not inherit the parent's"
    assert "DB_PASSWORD" not in env
    assert "JWT_SECRET_KEY" not in env


@pytest.mark.unit
def test_command_injection_via_install_cmd_is_impossible():
    """install_cmd is a bool (use_ci), never a free-form string — there is no
    code path through which a caller can inject a shell command here."""
    import inspect

    sig = inspect.signature(run_vite_build)
    assert "use_ci" in sig.parameters
    assert sig.parameters["use_ci"].annotation in (bool, "bool")
    assert "command" not in sig.parameters
    assert "cmd" not in sig.parameters
