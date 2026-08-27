"""Unit tests for app/static_sites/nextjs_runtime.py — runtime container
start/health-check/stop. No real Docker daemon; subprocess.run and the
health-probe HTTP call are mocked throughout.
"""
from __future__ import annotations

import subprocess
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.static_sites import nextjs_runtime as rt


def _enable(monkeypatch, **overrides):
    monkeypatch.setattr(rt.settings, "NEXTJS_BUILD_ENABLED", True, raising=False)
    monkeypatch.setattr(rt.settings, "VITE_BUILD_ORCHESTRATOR_URL", "", raising=False)  # force direct mode
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


def _mock_docker_run_ok(argv, **kwargs):
    return MagicMock(returncode=0, stdout="containerid123", stderr="")


@pytest.mark.unit
def test_runtime_disabled_by_default_raises_clear_error(tmp_path):
    with patch("app.static_sites.nextjs_runtime.settings") as s:
        s.NEXTJS_BUILD_ENABLED = False
        with pytest.raises(rt.RuntimeError_, match="not enabled"):
            rt.start_runtime(artifact_dir=tmp_path, deployment_id=uuid.uuid4())


@pytest.mark.unit
def test_container_name_is_deterministic_and_matches_pattern():
    dep_id = uuid.uuid4()
    name = rt.container_name(dep_id)
    assert name == f"thtwaat-nextjs-runtime-{dep_id.hex}"
    assert rt.CONTAINER_NAME_RE.match(name)


@pytest.mark.unit
def test_proxy_target_is_name_colon_port(monkeypatch):
    _enable(monkeypatch)
    assert rt.proxy_target("thtwaat-nextjs-runtime-abc") == f"thtwaat-nextjs-runtime-abc:{rt.settings.NEXTJS_RUNTIME_PORT}"


@pytest.mark.unit
def test_start_runtime_argv_has_no_docker_socket_no_published_port(tmp_path, monkeypatch):
    _enable(monkeypatch)
    dep_id = uuid.uuid4()
    name = rt.container_name(dep_id)

    calls = []

    def _fake_run(argv, **kwargs):
        calls.append(argv)
        return MagicMock(returncode=0, stdout="cid", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(rt, "_is_running_direct", lambda name: True)
    monkeypatch.setattr(rt, "_probe_health", lambda url, timeout: (True, 200))
    monkeypatch.setattr(rt, "_container_ip", lambda name, network: "172.20.0.5")

    result = rt.start_runtime(artifact_dir=tmp_path, deployment_id=dep_id)

    run_argv = calls[0]
    assert run_argv[:3] == ["docker", "run", "-d"]
    assert "/var/run/docker.sock" not in " ".join(run_argv)
    assert "-p" not in run_argv  # no published host port anywhere
    assert "--cap-drop" in run_argv and "ALL" in run_argv
    assert "--security-opt" in run_argv and "no-new-privileges" in run_argv
    assert "--user" in run_argv and "1000:1000" in run_argv
    assert "--read-only" in run_argv
    assert "--network" in run_argv and "thtwaat_nextjs_runtime_net" in run_argv
    assert "--memory" in run_argv
    assert "--pids-limit" in run_argv
    mounts = [run_argv[i + 1] for i, a in enumerate(run_argv) if a == "-v"]
    assert len(mounts) == 1
    assert mounts[0].endswith(":/app:ro")
    assert result.healthy is True
    assert result.container_name == name


@pytest.mark.unit
def test_start_runtime_stops_container_on_start_failure(tmp_path, monkeypatch):
    _enable(monkeypatch)
    dep_id = uuid.uuid4()

    stopped = {"called": False}

    def _fake_run(argv, **kwargs):
        if argv[:2] == ["docker", "run"]:
            return MagicMock(returncode=1, stdout="", stderr="failed to start")
        if argv[:2] in (["docker", "stop"], ["docker", "rm"]):
            stopped["called"] = True
            return MagicMock(returncode=0)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(rt.RuntimeError_, match="failed to start"):
        rt.start_runtime(artifact_dir=tmp_path, deployment_id=dep_id)

    assert stopped["called"] is True


@pytest.mark.unit
def test_start_runtime_stops_container_when_health_check_never_passes(tmp_path, monkeypatch):
    _enable(monkeypatch)
    dep_id = uuid.uuid4()

    stop_calls = []

    def _fake_run(argv, **kwargs):
        if argv[:2] == ["docker", "run"]:
            return MagicMock(returncode=0, stdout="cid", stderr="")
        if argv[:2] in (["docker", "stop"], ["docker", "rm"]):
            stop_calls.append(argv)
            return MagicMock(returncode=0)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(rt, "_is_running_direct", lambda name: True)
    monkeypatch.setattr(rt, "_container_ip", lambda name, network: "172.20.0.5")
    monkeypatch.setattr(rt, "_probe_health", lambda url, timeout: (False, 503))

    with pytest.raises(rt.RuntimeError_, match="failed its health check"):
        rt.start_runtime(artifact_dir=tmp_path, deployment_id=dep_id)

    assert len(stop_calls) >= 1


@pytest.mark.unit
def test_stop_runtime_rejects_names_outside_naming_convention():
    """A caller can never point stop_runtime at an arbitrary container —
    only the fixed thtwaat-nextjs-runtime-<hex> pattern is ever accepted."""
    with pytest.raises(rt.RuntimeError_, match="Invalid runtime container name"):
        rt.stop_runtime("some-other-container")
    with pytest.raises(rt.RuntimeError_):
        rt.stop_runtime("thtwaat-api")


@pytest.mark.unit
def test_is_running_returns_false_for_invalid_name_without_calling_docker(monkeypatch):
    called = {"n": 0}

    def _fake_run(*a, **kw):
        called["n"] += 1
        return MagicMock(returncode=0, stdout="true\n")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert rt.is_running("not-a-runtime-container") is False
    assert called["n"] == 0


@pytest.mark.unit
def test_stop_runtime_is_idempotent_on_missing_container(monkeypatch):
    name = rt.container_name(uuid.uuid4())

    def _fake_run(argv, **kwargs):
        return MagicMock(returncode=1, stdout="", stderr="No such container")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    rt.stop_runtime(name)  # must not raise
