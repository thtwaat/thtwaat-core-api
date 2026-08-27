"""Static-configuration assertions for the Phase 2 hardening pass — items
that are true by construction of docker-compose.prod.yml / the orchestrator
service's request schema, not something a live Docker daemon is needed to
prove. See the Phase 2 staging validation report for the live (Docker
Desktop) tests that cover the parts these can't: real network isolation,
real metadata-SSRF blocking, a real end-to-end orchestrator build.

Items A, C, D, E, F from that report's follow-up hardening request.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"


def _load_compose_prod() -> dict:
    return yaml.safe_load(COMPOSE_PROD.read_text(encoding="utf-8"))


# ---- A. api/worker/web_app never get Docker socket access ------------------


@pytest.mark.unit
def test_only_docker_socket_proxy_mounts_the_real_socket():
    compose = _load_compose_prod()
    services = compose["services"]

    offenders = []
    for name, svc in services.items():
        for vol in svc.get("volumes", []) or []:
            vol_str = vol if isinstance(vol, str) else vol.get("source", "")
            if "docker.sock" in vol_str and name != "docker-socket-proxy":
                offenders.append(name)

    assert offenders == [], (
        f"docker.sock must only ever be mounted into docker-socket-proxy, found in: {offenders}"
    )
    assert "docker.sock" in " ".join(services["docker-socket-proxy"].get("volumes", []))


@pytest.mark.unit
@pytest.mark.parametrize("service_name", ["api", "worker", "web_app"])
def test_service_has_no_docker_host_env_pointing_at_raw_socket(service_name):
    compose = _load_compose_prod()
    env = compose["services"][service_name].get("environment", {}) or {}
    assert "DOCKER_HOST" not in env, (
        f"{service_name} must never be configured to talk to a Docker daemon directly"
    )


# ---- E. build container's network is never attached to a persistent service ----


@pytest.mark.unit
def test_vite_build_network_never_attached_to_any_persistent_service():
    """thtwaat_vite_build_net must only ever be used ad-hoc by `docker run`
    (see app/static_sites/vite_build.py / orchestrator/app/build.py) — if it
    ever shows up under a service's `networks:` list, that service would sit
    on the same L2 segment as the untrusted build containers permanently."""
    compose = _load_compose_prod()
    assert "thtwaat_vite_build_net" in compose["networks"], "must still be declared for `docker run --network` to use"

    for name, svc in compose["services"].items():
        attached = svc.get("networks", []) or []
        assert "thtwaat_vite_build_net" not in attached, (
            f"service {name!r} must not be permanently attached to the untrusted build network"
        )


@pytest.mark.unit
def test_api_worker_not_on_socket_proxy_network():
    """api/worker may reach build-orchestrator (thtwaat_orchestrator_net)
    but must have no path to docker-socket-proxy (thtwaat_socket_proxy_net)
    — that's the actual defense-in-depth property (see orchestrator/README.md)."""
    compose = _load_compose_prod()
    for name in ("api", "worker"):
        attached = compose["services"][name].get("networks", []) or []
        assert "thtwaat_orchestrator_net" in attached
        assert "thtwaat_socket_proxy_net" not in attached


@pytest.mark.unit
def test_only_orchestrator_and_proxy_on_socket_proxy_network():
    compose = _load_compose_prod()
    members = [
        name for name, svc in compose["services"].items()
        if "thtwaat_socket_proxy_net" in (svc.get("networks", []) or [])
    ]
    assert set(members) == {"build-orchestrator", "docker-socket-proxy"}


# ---- B/C/D. orchestrator accepts only UUIDs + a fixed enum, nothing else ----


@pytest.fixture(scope="module", autouse=True)
def _orchestrator_on_path():
    orch_dir = str(REPO_ROOT / "orchestrator")
    if orch_dir not in sys.path:
        sys.path.insert(0, orch_dir)
    yield
    if orch_dir in sys.path:
        sys.path.remove(orch_dir)


@pytest.mark.unit
def test_orchestrator_request_schema_rejects_unknown_fields(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.main", None)
    sys.modules.pop("orchestrator_app.settings", None)
    sys.modules.pop("orchestrator_app.build", None)
    from orchestrator_app.main import BuildRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BuildRequest.model_validate({
            "workspace_id": "11111111-1111-1111-1111-111111111111",
            "site_id": "22222222-2222-2222-2222-222222222222",
            "deployment_id": "33333333-3333-3333-3333-333333333333",
            "install_cmd": "ci",
            "image": "evil:latest",  # not a real field — must be rejected, not ignored
        })


@pytest.mark.unit
def test_orchestrator_request_schema_has_no_path_or_command_fields(monkeypatch):
    """The attack surface: UUIDs, a two-value enum, and (THTWAAT Deploy
    Phase 4B) a bounded, validated env_vars dict — never a path, image name,
    or docker argument. If this ever grows a field like `source_dir`,
    `image`, or `docker_args`, that field becomes a way for a compromised
    api/worker to ask the orchestrator to do something other than build the
    already-staged deployment_id."""
    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.main", None)
    from orchestrator_app.main import BuildRequest

    assert set(BuildRequest.model_fields) == {"workspace_id", "site_id", "deployment_id", "install_cmd", "env_vars"}
    assert BuildRequest.model_config.get("extra") == "forbid"
    for forbidden in ("source_dir", "dest_dir", "image", "path", "mount", "volume", "docker_args", "command"):
        assert forbidden not in BuildRequest.model_fields


@pytest.mark.unit
def test_orchestrator_build_computes_every_path_itself(monkeypatch):
    """orchestrator_app.build.run_build's signature never accepts a path,
    image name, or docker argument from its caller — every filesystem
    location it uses is derived from workspace_id/site_id/deployment_id
    against its own STATIC_SITES_DIR setting (see
    orchestrator_app/build.py's module docstring). Phase 4B's env_vars
    param is a bounded, validated dict of KEY=VALUE pairs — not a path,
    image, or command — see main.py's BuildRequest validator."""
    import inspect

    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.build", None)
    from orchestrator_app.build import run_build

    params = set(inspect.signature(run_build).parameters)
    assert params == {"workspace_id", "site_id", "deployment_id", "install_cmd", "env_vars"}
    for forbidden in ("source_dir", "dest_dir", "image", "path", "mount", "volume", "docker_args", "command"):
        assert forbidden not in params


# ---- THTWAAT Phase 3 — Next.js runtime network isolation --------------------


@pytest.mark.unit
def test_nextjs_runtime_network_only_attached_to_nginx_and_orchestrator():
    """thtwaat_nextjs_runtime_net must never reach db/redis/api/worker — only
    nginx (to proxy to a runtime container) and build-orchestrator (to
    health-probe one it just started) sit on it as compose services; every
    actual runtime container joins ad-hoc via `docker run --network`, never
    as a declared service."""
    compose = _load_compose_prod()
    assert "thtwaat_nextjs_runtime_net" in compose["networks"]
    assert compose["networks"]["thtwaat_nextjs_runtime_net"].get("internal") is True

    members = [
        name for name, svc in compose["services"].items()
        if "thtwaat_nextjs_runtime_net" in (svc.get("networks", []) or [])
    ]
    assert set(members) == {"nginx", "build-orchestrator"}


@pytest.mark.unit
@pytest.mark.parametrize("service_name", ["api", "worker", "db", "redis", "web_app"])
def test_nextjs_runtime_network_never_reaches_core_services(service_name):
    compose = _load_compose_prod()
    attached = compose["services"][service_name].get("networks", []) or []
    assert "thtwaat_nextjs_runtime_net" not in attached


@pytest.mark.unit
def test_nextjs_runtime_containers_never_get_published_host_ports():
    """No compose service publishes NEXTJS_RUNTIME_PORT — runtime containers
    are never declared services in the first place (started ad-hoc by the
    orchestrator, see orchestrator_app/nextjs_runtime.py), and none of the
    ad-hoc `docker run` invocations ever pass -p/--publish (see that
    module's argv construction, asserted directly in
    tests/unit/static_sites/test_nextjs_runtime.py)."""
    compose = _load_compose_prod()
    for name, svc in compose["services"].items():
        for port in svc.get("ports", []) or []:
            assert "3000" not in str(port), f"service {name!r} must not publish the Next.js runtime port"


# ---- Next.js orchestrator request schemas: narrow attack surface only ------


@pytest.mark.unit
def test_orchestrator_nextjs_build_schema_has_no_path_or_command_fields(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.main", None)
    from orchestrator_app.main import NextjsBuildRequest

    assert set(NextjsBuildRequest.model_fields) == {
        "workspace_id", "site_id", "deployment_id", "install_cmd", "env_vars",
    }
    assert NextjsBuildRequest.model_config.get("extra") == "forbid"


@pytest.mark.unit
def test_orchestrator_nextjs_runtime_start_schema_has_no_path_or_command_fields(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.main", None)
    from orchestrator_app.main import NextjsRuntimeStartRequest

    assert set(NextjsRuntimeStartRequest.model_fields) == {
        "workspace_id", "site_id", "artifact_id", "deployment_id", "env_vars",
    }
    assert NextjsRuntimeStartRequest.model_config.get("extra") == "forbid"


@pytest.mark.unit
def test_orchestrator_nextjs_runtime_stop_and_inspect_validate_container_name(monkeypatch):
    """The container_name PATH parameter on DELETE/GET /v1/nextjs-runtimes/{}
    must be checked against the fixed naming convention before it ever
    reaches a docker command — proven directly against the validating
    functions (is_running()/_validate_name() via stop_runtime()), not just
    by inspecting the route signature."""
    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.nextjs_runtime", None)
    from orchestrator_app.nextjs_runtime import RuntimeError_, is_running, stop_runtime

    assert is_running("thtwaat-api") is False
    assert is_running("../../etc/passwd") is False
    with pytest.raises(RuntimeError_):
        stop_runtime("thtwaat-docker-socket-proxy")


@pytest.mark.unit
def test_orchestrator_nextjs_build_computes_every_path_itself(monkeypatch):
    import inspect

    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.nextjs_build", None)
    from orchestrator_app.nextjs_build import run_build as run_nextjs_build

    params = set(inspect.signature(run_nextjs_build).parameters)
    assert params == {"workspace_id", "site_id", "deployment_id", "install_cmd", "env_vars"}
    for forbidden in ("source_dir", "dest_dir", "image", "path", "mount", "volume", "docker_args", "command"):
        assert forbidden not in params


@pytest.mark.unit
def test_orchestrator_nextjs_runtime_start_computes_every_path_itself(monkeypatch):
    import inspect

    monkeypatch.setenv("ORCHESTRATOR_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("STATIC_SITES_HOST_DIR", "/tmp/static-sites")
    sys.modules.pop("orchestrator_app.nextjs_runtime", None)
    from orchestrator_app.nextjs_runtime import start_runtime

    params = set(inspect.signature(start_runtime).parameters)
    assert params == {"workspace_id", "site_id", "artifact_id", "deployment_id", "env_vars"}
    for forbidden in ("source_dir", "dest_dir", "image", "path", "mount", "volume", "docker_args", "command", "port"):
        assert forbidden not in params
