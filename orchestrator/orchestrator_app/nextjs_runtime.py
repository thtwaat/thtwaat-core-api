"""The actual `docker run`/stop/inspect invocations for Next.js RUNTIME
containers — the production-mode counterpart of
app/static_sites/nextjs_runtime.py's direct-mode functions.

This service is attached to NEXTJS_RUNTIME_NETWORK itself (see
docker-compose.prod.yml), so — unlike the api/worker host in direct/dev
mode, which has to resolve a container's bridge-network IP via `docker
inspect` — it can health-probe a freshly started runtime container by its
plain container name over Docker's embedded DNS, exactly like nginx will.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from orchestrator_app.settings import settings

logger = logging.getLogger(__name__)

CONTAINER_NAME_RE = re.compile(r"^thtwaat-nextjs-runtime-[0-9a-f]{32}$")


class RuntimeError_(Exception):  # noqa: N818
    def __init__(self, message: str, *, log_lines: Optional[List[str]] = None):
        super().__init__(message)
        self.log_lines = log_lines or []


@dataclass
class RuntimeStartResult:
    container_name: str
    healthy: bool
    status_code: Optional[int] = None
    log_lines: List[str] = field(default_factory=list)


def container_name(deployment_id: UUID) -> str:
    return f"thtwaat-nextjs-runtime-{deployment_id.hex}"


def _validate_name(name: str) -> None:
    if not CONTAINER_NAME_RE.match(name):
        raise RuntimeError_("Invalid runtime container name")


def _docker_env() -> dict:
    env = {"PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")}
    if settings.DOCKER_HOST:
        env["DOCKER_HOST"] = settings.DOCKER_HOST
    return env


def _host_path(container_path: Path) -> str:
    internal_root = Path(settings.STATIC_SITES_DIR).resolve()
    rel = container_path.resolve().relative_to(internal_root)
    return str(Path(settings.STATIC_SITES_HOST_DIR) / rel).replace("\\", "/")


def _run(cmd: List[str], *, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False, env=_docker_env())


def stop_runtime(name: str) -> None:
    if not name:
        return
    _validate_name(name)
    for cmd in (["docker", "stop", "-t", "10", name], ["docker", "rm", "-f", name]):
        try:
            _run(cmd, timeout=25)
        except Exception:  # noqa: BLE001
            pass


def is_running(name: str) -> bool:
    if not name or not CONTAINER_NAME_RE.match(name):
        return False
    try:
        proc = _run(["docker", "inspect", "-f", "{{.State.Running}}", name], timeout=10)
    except Exception:  # noqa: BLE001
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _probe_health(url: str, timeout: float) -> tuple[bool, Optional[int]]:
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "thtwaat-orchestrator-health"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode())
            return 200 <= code < 500, code
    except urllib.error.HTTPError as exc:
        return 200 <= int(exc.code) < 500, int(exc.code)
    except Exception:  # noqa: BLE001
        return False, None


_RESERVED_RUNTIME_KEYS = {"PORT", "HOSTNAME", "NODE_ENV"}


def start_runtime(
    *,
    workspace_id: UUID,
    site_id: UUID,
    artifact_id: UUID,
    deployment_id: UUID,
    env_vars: Optional[Dict[str, str]] = None,
) -> RuntimeStartResult:
    root = Path(settings.STATIC_SITES_DIR).resolve()
    artifact_dir = root / str(workspace_id) / str(site_id) / str(artifact_id)
    if not artifact_dir.is_dir():
        raise RuntimeError_("Deployment artifact directory does not exist")

    # Defense in depth — main.py's NextjsRuntimeStartRequest validator
    # already strips these, but this function never trusts a caller alone.
    env_vars = {k: v for k, v in (env_vars or {}).items() if k not in _RESERVED_RUNTIME_KEYS}

    name = container_name(deployment_id)
    port = int(settings.NEXTJS_RUNTIME_PORT)

    argv = [
        "docker", "run",
        "-d",
        "--name", name,
        "--network", settings.NEXTJS_RUNTIME_NETWORK,
        "--memory", f"{settings.NEXTJS_RUNTIME_MEMORY_MB}m",
        "--memory-swap", f"{settings.NEXTJS_RUNTIME_MEMORY_MB}m",
        "--cpus", str(settings.NEXTJS_RUNTIME_CPU),
        "--pids-limit", str(settings.NEXTJS_RUNTIME_PIDS),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "1000:1000",
        "--read-only",
        "--tmpfs", f"/tmp:rw,size={settings.NEXTJS_RUNTIME_TMPFS_MB}m,mode=1777",
        "-v", f"{_host_path(artifact_dir)}:/app:ro",
        "-e", f"PORT={port}",
        "-e", "HOSTNAME=0.0.0.0",
        "-e", "NODE_ENV=production",
    ]
    for key, value in env_vars.items():
        argv += ["-e", f"{key}={value}"]
    argv.append(settings.NEXTJS_RUNTIME_IMAGE)

    logger.info(
        "orchestrator_nextjs_runtime_start deployment_id=%s container=%s env_var_count=%s",
        deployment_id, name, len(env_vars),
    )

    try:
        proc = _run(argv, timeout=30)
    except FileNotFoundError:
        raise RuntimeError_("Docker is not available to the build orchestrator.") from None

    log_lines = [l for l in (proc.stdout.strip(), proc.stderr.strip()) if l]
    if proc.returncode != 0:
        stop_runtime(name)
        raise RuntimeError_("Runtime container failed to start. See logs for details.", log_lines=log_lines)

    deadline = time.monotonic() + settings.NEXTJS_HEALTH_STARTUP_TIMEOUT_SECONDS
    attempts = 0
    last_code: Optional[int] = None
    while time.monotonic() < deadline and attempts < settings.NEXTJS_HEALTH_RETRY_COUNT:
        attempts += 1
        if not is_running(name):
            stop_runtime(name)
            raise RuntimeError_("Runtime container exited before becoming healthy.", log_lines=log_lines)
        ok, last_code = _probe_health(f"http://{name}:{port}/", settings.NEXTJS_HEALTH_REQUEST_TIMEOUT_SECONDS)
        if ok:
            logger.info(
                "orchestrator_nextjs_runtime_healthy deployment_id=%s container=%s status_code=%s",
                deployment_id, name, last_code,
            )
            return RuntimeStartResult(container_name=name, healthy=True, status_code=last_code, log_lines=log_lines)
        time.sleep(settings.NEXTJS_HEALTH_RETRY_INTERVAL_SECONDS)

    stop_runtime(name)
    raise RuntimeError_("Runtime container failed its health check within the startup timeout.", log_lines=log_lines)
