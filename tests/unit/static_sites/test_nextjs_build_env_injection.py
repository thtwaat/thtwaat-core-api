"""Unit tests for THTWAAT Deploy Phase 4B environment-variable injection in
app/static_sites/nextjs_build.py — NEXT_PUBLIC_* client build vars only,
both direct and orchestrator dispatch modes. Server-only secrets must never
reach the BUILD step (they go through nextjs_runtime.py instead)."""
from __future__ import annotations

import subprocess
import uuid
from unittest.mock import MagicMock

import pytest

from app.static_sites.nextjs_build import NextjsBuildError, run_nextjs_build


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
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)
    for k, v in overrides.items():
        monkeypatch.setattr(f"app.static_sites.nextjs_build.settings.{k}", v, raising=False)


def _run_direct(monkeypatch, tmp_path, *, public_env_vars):
    _enable(monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "server.js").write_text("// standalone")
        (dest / ".next" / "static").mkdir(parents=True)
        return MagicMock(returncode=0, stdout="build ok", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_nextjs_build(
        source_dir=src, dest_dir=dest, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(), site_id=uuid.uuid4(),
        use_ci=True, public_env_vars=public_env_vars,
    )
    return captured["argv"]


def _env_flags(argv):
    return {argv[i + 1] for i, a in enumerate(argv) if a == "-e"}


@pytest.mark.unit
def test_next_public_var_injected_at_build_direct_mode(tmp_path, monkeypatch):
    argv = _run_direct(monkeypatch, tmp_path, public_env_vars={"NEXT_PUBLIC_API_URL": "https://api.example.com"})
    assert "NEXT_PUBLIC_API_URL=https://api.example.com" in _env_flags(argv)


@pytest.mark.unit
def test_server_only_vars_not_injected_into_client_build(tmp_path, monkeypatch):
    argv = _run_direct(
        monkeypatch, tmp_path,
        public_env_vars={
            "NEXT_PUBLIC_API_URL": "https://api.example.com",
            "DATABASE_URL": "postgres://super-secret",
            "OPENAI_API_KEY": "super-secret-api-key",
            "STRIPE_SECRET_KEY": "super-secret-stripe-key",
            "JWT_SECRET": "super-secret-jwt",
            "INTERNAL_API_KEY": "super-secret-internal",
        },
    )
    flags = " ".join(argv)
    assert "NEXT_PUBLIC_API_URL=https://api.example.com" in flags
    for secret in ("super-secret", "super-secret-api-key", "super-secret-stripe-key", "super-secret-jwt", "super-secret-internal"):
        assert secret not in flags


@pytest.mark.unit
def test_too_many_env_vars_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    too_many = {f"NEXT_PUBLIC_VAR_{i}": "v" for i in range(101)}
    with pytest.raises(NextjsBuildError, match="Too many"):
        run_nextjs_build(
            source_dir=src, dest_dir=tmp_path / "dest", deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
            site_id=uuid.uuid4(), use_ci=True, public_env_vars=too_many,
        )


# ---- orchestrator mode --------------------------------------------------------


@pytest.mark.unit
def test_orchestrator_payload_only_carries_next_public_prefixed_vars(monkeypatch, tmp_path):
    _enable(monkeypatch, VITE_BUILD_ORCHESTRATOR_URL="http://build-orchestrator:9000")
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.VITE_BUILD_ORCHESTRATOR_SHARED_SECRET", "shh", raising=False)
    monkeypatch.setattr("app.static_sites.nextjs_build.settings.VITE_BUILD_ORCHESTRATOR_TIMEOUT_SECONDS", 30, raising=False)

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

    run_nextjs_build(
        source_dir=tmp_path, dest_dir=tmp_path, deployment_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        site_id=uuid.uuid4(), use_ci=True,
        public_env_vars={"NEXT_PUBLIC_API_URL": "https://api.example.com", "STRIPE_SECRET_KEY": "super-secret-stripe-key"},
    )

    sent_env_vars = captured["json"]["env_vars"]
    assert sent_env_vars == {"NEXT_PUBLIC_API_URL": "https://api.example.com"}
    assert "STRIPE_SECRET_KEY" not in sent_env_vars
