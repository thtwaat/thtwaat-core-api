"""THTWAAT Deploy Phase 4B — tests for orchestrator_app's env_vars request
validation and injection. This package is a standalone deployable unit (see
orchestrator_app/build.py's docstring) with no dependency on the main
app.* package, so its tests live here rather than under the repo's tests/
tree. Run from the orchestrator/ directory:

    cd orchestrator
    ORCHESTRATOR_SHARED_SECRET=test STATIC_SITES_HOST_DIR=/tmp/static-sites \
        python -m pytest tests/test_env_vars.py -q
"""
from __future__ import annotations

import os
import subprocess
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ.setdefault("ORCHESTRATOR_SHARED_SECRET", "test-secret")
os.environ.setdefault("STATIC_SITES_HOST_DIR", "/tmp/static-sites-host")

from orchestrator_app.main import BuildRequest, NextjsBuildRequest, NextjsRuntimeStartRequest, app

AUTH = {"Authorization": "Bearer test-secret"}


# ---- request schema validation -------------------------------------------------


def test_vite_build_request_accepts_vite_prefixed_vars():
    req = BuildRequest(
        workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
        install_cmd="ci", env_vars={"VITE_API_URL": "https://api.example.com"},
    )
    assert req.env_vars == {"VITE_API_URL": "https://api.example.com"}


def test_vite_build_request_rejects_non_vite_var():
    with pytest.raises(ValidationError):
        BuildRequest(
            workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
            install_cmd="ci", env_vars={"DATABASE_URL": "postgres://super-secret"},
        )


def test_vite_build_request_rejects_invalid_key_shape():
    with pytest.raises(ValidationError):
        BuildRequest(
            workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
            install_cmd="ci", env_vars={"VITE_bad-key": "v"},
        )


def test_nextjs_build_request_accepts_next_public_only():
    req = NextjsBuildRequest(
        workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
        install_cmd="ci", env_vars={"NEXT_PUBLIC_API_URL": "https://api.example.com"},
    )
    assert req.env_vars == {"NEXT_PUBLIC_API_URL": "https://api.example.com"}


def test_nextjs_build_request_rejects_server_only_var():
    with pytest.raises(ValidationError):
        NextjsBuildRequest(
            workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
            install_cmd="ci", env_vars={"STRIPE_SECRET_KEY": "super-secret-stripe-key"},
        )


def test_nextjs_runtime_request_accepts_any_valid_key():
    req = NextjsRuntimeStartRequest(
        workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), artifact_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
        env_vars={"DATABASE_URL": "postgres://super-secret", "NEXT_PUBLIC_API_URL": "https://api.example.com"},
    )
    assert req.env_vars["DATABASE_URL"] == "postgres://super-secret"


def test_nextjs_runtime_request_strips_reserved_keys():
    req = NextjsRuntimeStartRequest(
        workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), artifact_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
        env_vars={"PORT": "9999", "HOSTNAME": "evil", "NODE_ENV": "dev", "DATABASE_URL": "postgres://x"},
    )
    assert req.env_vars == {"DATABASE_URL": "postgres://x"}


def test_env_vars_over_max_count_rejected():
    too_many = {f"VITE_VAR_{i}": "v" for i in range(101)}
    with pytest.raises(ValidationError):
        BuildRequest(
            workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
            install_cmd="ci", env_vars=too_many,
        )


def test_env_var_value_with_null_byte_rejected():
    with pytest.raises(ValidationError):
        BuildRequest(
            workspace_id=uuid.uuid4(), site_id=uuid.uuid4(), deployment_id=uuid.uuid4(),
            install_cmd="ci", env_vars={"VITE_X": "abc\x00def"},
        )


# ---- endpoint-level (auth + validation wired together) -------------------------


def test_vite_build_endpoint_rejects_server_only_var_with_422():
    client = TestClient(app)
    resp = client.post(
        "/v1/vite-builds",
        json={
            "workspace_id": str(uuid.uuid4()), "site_id": str(uuid.uuid4()), "deployment_id": str(uuid.uuid4()),
            "install_cmd": "ci", "env_vars": {"DATABASE_URL": "postgres://super-secret"},
        },
        headers=AUTH,
    )
    assert resp.status_code == 422
    assert "super-secret" not in resp.text


def test_vite_build_endpoint_requires_shared_secret():
    client = TestClient(app)
    resp = client.post(
        "/v1/vite-builds",
        json={
            "workspace_id": str(uuid.uuid4()), "site_id": str(uuid.uuid4()), "deployment_id": str(uuid.uuid4()),
            "install_cmd": "ci", "env_vars": {"VITE_X": "y"},
        },
    )
    assert resp.status_code == 401


# ---- argv injection (build.py / nextjs_build.py / nextjs_runtime.py) -----------


def test_build_py_only_injects_vite_prefixed_vars_into_argv(tmp_path, monkeypatch):
    from orchestrator_app import build

    monkeypatch.setattr(build.settings, "STATIC_SITES_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(build.settings, "STATIC_SITES_HOST_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(build.settings, "VITE_BUILD_EGRESS_PROXY_URL", "", raising=False)
    monkeypatch.setattr(build.settings, "VITE_MAX_OUTPUT_FILE_COUNT", 20000, raising=False)
    monkeypatch.setattr(build.settings, "VITE_MAX_OUTPUT_BYTES", 100 * 1024 * 1024, raising=False)

    deployment_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    site_id = uuid.uuid4()
    staging = tmp_path / "_staging" / str(deployment_id)
    staging.mkdir(parents=True)
    dest = tmp_path / str(workspace_id) / str(site_id) / str(deployment_id)

    captured = {}

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text("<html></html>")
        return MagicMock(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    build.run_build(
        workspace_id=workspace_id, site_id=site_id, deployment_id=deployment_id, install_cmd="ci",
        env_vars={"VITE_API_URL": "https://api.example.com", "DATABASE_URL": "postgres://super-secret"},
    )

    flags = " ".join(captured["argv"])
    assert "VITE_API_URL=https://api.example.com" in flags
    assert "super-secret" not in flags


def test_nextjs_runtime_py_never_lets_user_override_port(tmp_path, monkeypatch):
    from orchestrator_app import nextjs_runtime as rt

    monkeypatch.setattr(rt.settings, "STATIC_SITES_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(rt.settings, "STATIC_SITES_HOST_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_RUNTIME_PORT", 3000, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_HEALTH_STARTUP_TIMEOUT_SECONDS", 1, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_HEALTH_RETRY_COUNT", 1, raising=False)
    monkeypatch.setattr(rt.settings, "NEXTJS_HEALTH_RETRY_INTERVAL_SECONDS", 0.01, raising=False)

    workspace_id, site_id, artifact_id, deployment_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    artifact_dir = tmp_path / str(workspace_id) / str(site_id) / str(artifact_id)
    artifact_dir.mkdir(parents=True)

    captured = {}

    def _fake_run(cmd, **kwargs):
        if cmd[:2] == ["docker", "run"]:
            captured["argv"] = cmd
        return MagicMock(returncode=0, stdout="containerid", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(rt, "is_running", lambda name: True)
    monkeypatch.setattr(rt, "_probe_health", lambda url, timeout: (True, 200))

    rt.start_runtime(
        workspace_id=workspace_id, site_id=site_id, artifact_id=artifact_id, deployment_id=deployment_id,
        env_vars={"PORT": "9999", "DATABASE_URL": "postgres://super-secret"},
    )

    flags = " ".join(captured["argv"])
    assert "PORT=9999" not in flags
    assert "PORT=3000" in flags
    assert "DATABASE_URL=postgres://super-secret" in flags
