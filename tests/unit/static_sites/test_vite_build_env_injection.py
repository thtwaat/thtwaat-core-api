"""Unit tests for THTWAAT Deploy Phase 4B environment-variable injection in
app/static_sites/vite_build.py — VITE_* client vars only, both direct and
orchestrator dispatch modes. subprocess.run/httpx are mocked; no real Docker
daemon or orchestrator service required."""
from __future__ import annotations

import subprocess
import uuid
from unittest.mock import MagicMock

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
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)
    for k, v in overrides.items():
        monkeypatch.setattr(f"app.static_sites.vite_build.settings.{k}", v, raising=False)


def _run_direct(monkeypatch, tmp_path, *, client_env_vars):
    _enable(monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("<html>built</html>")
        return MagicMock(returncode=0, stdout="build ok", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_vite_build(
        source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(),
        use_ci=True, client_env_vars=client_env_vars,
    )
    return captured["argv"]


def _env_flags(argv):
    return {argv[i + 1] for i, a in enumerate(argv) if a == "-e"}


@pytest.mark.unit
def test_vite_prefixed_var_is_injected_direct_mode(tmp_path, monkeypatch):
    argv = _run_direct(monkeypatch, tmp_path, client_env_vars={"VITE_API_URL": "https://api.example.com"})
    assert "VITE_API_URL=https://api.example.com" in _env_flags(argv)


@pytest.mark.unit
def test_non_vite_var_is_never_injected_direct_mode(tmp_path, monkeypatch):
    argv = _run_direct(
        monkeypatch, tmp_path,
        client_env_vars={"VITE_API_URL": "https://api.example.com", "DATABASE_URL": "postgres://super-secret"},
    )
    flags = " ".join(argv)
    assert "VITE_API_URL=https://api.example.com" in flags
    assert "DATABASE_URL" not in flags
    assert "super-secret" not in flags


@pytest.mark.unit
def test_server_only_secrets_never_reach_vite_build_argv(tmp_path, monkeypatch):
    argv = _run_direct(
        monkeypatch, tmp_path,
        client_env_vars={
            "DATABASE_URL": "postgres://super-secret",
            "OPENAI_API_KEY": "super-secret-api-key",
            "STRIPE_SECRET_KEY": "super-secret-stripe-key",
        },
    )
    flags = " ".join(argv)
    assert "super-secret" not in flags
    assert "super-secret-api-key" not in flags
    assert "super-secret-stripe-key" not in flags


@pytest.mark.unit
def test_no_client_env_vars_means_no_extra_flags(tmp_path, monkeypatch):
    argv = _run_direct(monkeypatch, tmp_path, client_env_vars=None)
    fixed_flags = {"INSTALL_CMD=ci", "NODE_ENV=production", "CI=true", "NPM_CONFIG_FUND=false", "NPM_CONFIG_AUDIT=false"}
    extra = _env_flags(argv) - fixed_flags
    extra = {f for f in extra if not f.startswith("MAX_NODE_MODULES_BYTES=")}
    assert extra == set()


@pytest.mark.unit
def test_too_many_env_vars_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    too_many = {f"VITE_VAR_{i}": "v" for i in range(101)}
    with pytest.raises(BuildError, match="Too many"):
        run_vite_build(
            source_dir=src, dest_dir=tmp_path / "dest", deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
            site_id=uuid.uuid4(), use_ci=True, client_env_vars=too_many,
        )


# ---- orchestrator mode --------------------------------------------------------


@pytest.mark.unit
def test_orchestrator_payload_only_carries_vite_prefixed_vars(monkeypatch, tmp_path):
    _enable(monkeypatch, VITE_BUILD_ORCHESTRATOR_URL="http://build-orchestrator:9000")
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_BUILD_ORCHESTRATOR_SHARED_SECRET", "shh", raising=False)
    monkeypatch.setattr("app.static_sites.vite_build.settings.VITE_BUILD_ORCHESTRATOR_TIMEOUT_SECONDS", 30, raising=False)

    captured = {}

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"success": True, "file_count": 1, "total_bytes": 10, "log_lines": [], "duration_ms": 5}

    def _fake_post(url, json, headers, timeout):
        captured["json"] = json
        return _FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)

    run_vite_build(
        source_dir=tmp_path, dest_dir=tmp_path, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        site_id=uuid.uuid4(), use_ci=True,
        client_env_vars={"VITE_API_URL": "https://api.example.com", "DATABASE_URL": "postgres://super-secret"},
    )

    sent_env_vars = captured["json"]["env_vars"]
    assert sent_env_vars == {"VITE_API_URL": "https://api.example.com"}
    assert "DATABASE_URL" not in sent_env_vars
