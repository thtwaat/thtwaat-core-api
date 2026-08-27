"""Unit tests for THTWAAT Deploy Phase 4B environment-variable injection in
app/static_sites/nextjs_runtime.py — the runtime container is server-side
only, so it gets the FULL resolved environment (both NEXT_PUBLIC_* and
server-only secrets); the client-bundle boundary lives in nextjs_build.py,
not here. Reserved keys (PORT/HOSTNAME/NODE_ENV) can never be overridden."""
from __future__ import annotations

import subprocess
import uuid
from unittest.mock import MagicMock

import pytest

from app.static_sites import nextjs_runtime as rt


def _enable(monkeypatch, **overrides):
    monkeypatch.setattr(rt.settings, "NEXTJS_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr(rt.settings, "VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_IMAGE", "thtwaat-nextjs-runtime:20", raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_NETWORK", "thtwaat_nextjs_runtime_net", raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_PORT", 3000, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_MEMORY_MB", 512, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_CPU", 0.5, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_PIDS", 128, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_TMPFS_MB", 64, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_HEALTH_STARTUP_TIMEOUT_SECONDS", 5, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_HEALTH_RETRY_COUNT", 3, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_HEALTH_RETRY_INTERVAL_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_HEALTH_REQUEST_TIMEOUT_SECONDS", 1.0, raising=False)
    for k, v in overrides.items():
        monkeypatch.setattr(rt.settings, k, v, raising=False)


def _env_flags(argv):
    return {argv[i + 1] for i, a in enumerate(argv) if a == "-e"}


def _start(monkeypatch, tmp_path, *, server_env_vars):
    _enable(monkeypatch)
    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        return MagicMock(returncode=0, stdout="containerid123", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(rt, "_is_running_direct", lambda name: True)
    monkeypatch.setattr(rt, "_probe_health", lambda url, timeout: (True, 200))
    monkeypatch.setattr(rt, "_container_ip", lambda name, network: "172.20.0.5")

    rt.start_runtime(artifact_dir=tmp_path, deployment_id=uuid.uuid4(), server_env_vars=server_env_vars)
    return captured["argv"]


@pytest.mark.unit
def test_server_only_secret_is_injected_into_runtime(tmp_path, monkeypatch):
    argv = _start(monkeypatch, tmp_path, server_env_vars={"DATABASE_URL": "postgres://prod-db"})
    assert "DATABASE_URL=postgres://prod-db" in _env_flags(argv)


@pytest.mark.unit
def test_next_public_var_also_available_server_side(tmp_path, monkeypatch):
    """Matches real Next.js semantics — server code can read NEXT_PUBLIC_*
    too; only the client BUILD step is restricted to that subset."""
    argv = _start(monkeypatch, tmp_path, server_env_vars={"NEXT_PUBLIC_API_URL": "https://api.example.com"})
    assert "NEXT_PUBLIC_API_URL=https://api.example.com" in _env_flags(argv)


@pytest.mark.unit
def test_all_resolved_vars_present_together(tmp_path, monkeypatch):
    argv = _start(
        monkeypatch, tmp_path,
        server_env_vars={
            "NEXT_PUBLIC_API_URL": "https://api.example.com",
            "DATABASE_URL": "postgres://super-secret",
            "OPENAI_API_KEY": "super-secret-api-key",
            "STRIPE_SECRET_KEY": "super-secret-stripe-key",
        },
    )
    flags = _env_flags(argv)
    assert "NEXT_PUBLIC_API_URL=https://api.example.com" in flags
    assert "DATABASE_URL=postgres://super-secret" in flags
    assert "OPENAI_API_KEY=super-secret-api-key" in flags
    assert "STRIPE_SECRET_KEY=super-secret-stripe-key" in flags


@pytest.mark.unit
@pytest.mark.parametrize("reserved_key", ["PORT", "HOSTNAME", "NODE_ENV"])
def test_reserved_keys_cannot_be_overridden(tmp_path, monkeypatch, reserved_key):
    argv = _start(monkeypatch, tmp_path, server_env_vars={reserved_key: "attacker-controlled"})
    assert "attacker-controlled" not in " ".join(argv)


@pytest.mark.unit
def test_too_many_env_vars_rejected(tmp_path, monkeypatch):
    _enable(monkeypatch)
    too_many = {f"VAR_{i}": "v" for i in range(101)}
    with pytest.raises(rt.RuntimeError_, match="Too many"):
        rt.start_runtime(artifact_dir=tmp_path, deployment_id=uuid.uuid4(), server_env_vars=too_many)


@pytest.mark.unit
def test_no_env_vars_is_a_no_op(tmp_path, monkeypatch):
    argv = _start(monkeypatch, tmp_path, server_env_vars=None)
    fixed = {"PORT=3000", "HOSTNAME=0.0.0.0", "NODE_ENV=production"}
    assert _env_flags(argv) == fixed


# ---- orchestrator mode --------------------------------------------------------


@pytest.mark.unit
def test_orchestrator_payload_carries_full_server_env(monkeypatch, tmp_path):
    _enable(monkeypatch, VITE_BUILD_ORCHESTRATOR_URL="http://build-orchestrator:9000")
    monkeypatch.setattr(rt.settings, "VITE_BUILD_ORCHESTRATOR_SHARED_SECRET", "shh", raising=False)

    artifact_dir = tmp_path / "ws" / "site" / "artifact"
    artifact_dir.mkdir(parents=True)

    captured = {}

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"success": True, "healthy": True, "container_name": "thtwaat-nextjs-runtime-abc", "status_code": 200, "log_lines": []}

    def _fake_post(url, json, headers, timeout):
        captured["json"] = json
        return _FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "post", _fake_post)

    rt.start_runtime(
        artifact_dir=artifact_dir, deployment_id=uuid.uuid4(),
        server_env_vars={"DATABASE_URL": "postgres://super-secret", "PORT": "9999"},
    )

    sent = captured["json"]["env_vars"]
    assert sent["DATABASE_URL"] == "postgres://super-secret"
    assert "PORT" not in sent
