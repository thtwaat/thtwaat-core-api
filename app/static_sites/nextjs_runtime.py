"""THTWAAT Deploy — isolated Next.js standalone RUNTIME container lifecycle.

Sibling to nextjs_build.py, but instead of a one-shot `--rm` build container
this starts, health-checks, and later stops a long-lived, per-deployment-
version Node process. Same dual orchestrator/direct dispatch and the same
narrow-schema philosophy: every filesystem path is computed server-side from
UUIDs, and the container name this module ever operates on is always
`thtwaat-nextjs-runtime-<hex>` — CONTAINER_NAME_RE is checked before any
docker stop/rm/inspect call, so even a confused caller can never point a
lifecycle operation at an arbitrary container.

No host port is ever published (see docker/next-runtime/README.md) — nginx
reaches a runtime container by its fixed name over Docker's embedded DNS on
NEXTJS_RUNTIME_NETWORK (app/ssl/nginx_gen.py RUNTIME_PROXY_LOCATION_BLOCK).
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

from app.config.settings import settings

logger = logging.getLogger(__name__)

CONTAINER_NAME_RE = re.compile(r"^thtwaat-nextjs-runtime-[0-9a-f]{32}$")

# THTWAAT Deploy Phase 4B — the runtime container is server-side only (never
# a client bundle), so every resolved var for this deployment (both
# NEXT_PUBLIC_* and server-only secrets) is available to it via
# process.env — that matches real Next.js server semantics.
_MAX_ENV_VARS = 100


class RuntimeError_(Exception):  # noqa: N818 - avoid shadowing builtins.RuntimeError
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
    """Fixed, deterministic name for the runtime container of one deployment
    ROW — for a rollback that starts a fresh container from an older
    artifact, this is the NEW row's id, not the artifact's original owner
    (see StaticSiteService.rollback)."""
    return f"thtwaat-nextjs-runtime-{deployment_id.hex}"


def proxy_target(name: str) -> str:
    return f"{name}:{settings.NEXTJS_RUNTIME_PORT}"


def _validate_name(name: str) -> None:
    if not CONTAINER_NAME_RE.match(name):
        raise RuntimeError_("Invalid runtime container name")


# Fixed keys this module wires itself (container port/bind/mode) — a
# same-named user variable is dropped rather than allowed to collide, since
# `docker run -e KEY=A -e KEY=B` resolves to whichever -e was LAST on the
# argv and these three are load-bearing for nginx proxying/health checks.
_RESERVED_RUNTIME_KEYS = {"PORT", "HOSTNAME", "NODE_ENV"}


def _validate_env_vars(env_vars: Optional[Dict[str, str]]) -> Dict[str, str]:
    if not env_vars:
        return {}
    filtered = {k: v for k, v in env_vars.items() if k not in _RESERVED_RUNTIME_KEYS}
    if len(filtered) > _MAX_ENV_VARS:
        raise RuntimeError_(f"Too many environment variables for this runtime (max {_MAX_ENV_VARS}).")
    return filtered


def start_runtime(
    *,
    artifact_dir: Path,
    deployment_id: UUID,
    server_env_vars: Optional[Dict[str, str]] = None,
) -> RuntimeStartResult:
    """Start (and health-check) a runtime container for artifact_dir.

    artifact_dir must already contain a valid standalone build (server.js +
    .next/static — see nextjs_build.py). Dispatches to orchestrator or
    direct mode. On any failure — start error OR failed health check — the
    container is stopped/removed before raising, so a failed v2 never
    lingers (Phase 10/11: v1 must remain untouched and LIVE).

    server_env_vars (Phase 4B): this deployment's full resolved environment
    (from its immutable snapshot — see env_resolver.py), scoped to THIS
    container only. Never automatically exposed to any client bundle — that
    boundary is nextjs_build.py's public_env_vars filter, not this function.
    """
    if not getattr(settings, "NEXTJS_BUILD_ENABLED", False):
        raise RuntimeError_(
            "Next.js runtimes are not enabled on this deployment. Contact your platform operator."
        )

    env_vars = _validate_env_vars(server_env_vars)

    if getattr(settings, "VITE_BUILD_ORCHESTRATOR_URL", ""):
        return _start_runtime_via_orchestrator(
            artifact_dir=artifact_dir, deployment_id=deployment_id, env_vars=env_vars
        )
    return _start_runtime_direct(artifact_dir=artifact_dir, deployment_id=deployment_id, env_vars=env_vars)


def stop_runtime(name: str) -> None:
    """Idempotent stop+remove — a no-op if the container doesn't exist."""
    if not name:
        return
    _validate_name(name)
    if getattr(settings, "VITE_BUILD_ORCHESTRATOR_URL", ""):
        _stop_runtime_via_orchestrator(name)
        return
    _stop_runtime_direct(name)


def is_running(name: str) -> bool:
    if not name or not CONTAINER_NAME_RE.match(name):
        return False
    if getattr(settings, "VITE_BUILD_ORCHESTRATOR_URL", ""):
        return _is_running_via_orchestrator(name)
    return _is_running_direct(name)


# ---- direct mode (local/dev — requires Docker socket access) --------------


def _inspect(name: str) -> Optional[dict]:
    try:
        proc = subprocess.run(
            ["docker", "inspect", name], capture_output=True, text=True, timeout=10, check=False,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return None
    return data[0] if data else None


def _container_ip(name: str, network: str) -> Optional[str]:
    info = _inspect(name)
    if not info:
        return None
    nets = ((info.get("NetworkSettings") or {}).get("Networks") or {})
    net = nets.get(network)
    return net.get("IPAddress") if net else None


def _is_running_direct(name: str) -> bool:
    info = _inspect(name)
    if not info:
        return False
    return bool(((info.get("State") or {}).get("Running")))


def _stop_runtime_direct(name: str) -> None:
    for cmd in (["docker", "stop", "-t", "10", name], ["docker", "rm", "-f", name]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=20, check=False)
        except Exception:  # noqa: BLE001
            pass


def _probe_health(url: str, timeout: float) -> tuple[bool, Optional[int]]:
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "thtwaat-nextjs-health"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode())
            return 200 <= code < 500, code
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        return 200 <= code < 500, code
    except Exception:  # noqa: BLE001
        return False, None


def _start_runtime_direct(
    *, artifact_dir: Path, deployment_id: UUID, env_vars: Optional[Dict[str, str]] = None
) -> RuntimeStartResult:
    name = container_name(deployment_id)
    artifact_dir = Path(artifact_dir).resolve()
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
        "-v", f"{artifact_dir}:/app:ro",
        "-e", f"PORT={port}",
        "-e", "HOSTNAME=0.0.0.0",
        "-e", "NODE_ENV=production",
    ]
    # THTWAAT Deploy Phase 4B — this deployment's full resolved environment,
    # server-side only (never a client bundle). env_vars has already had
    # PORT/HOSTNAME/NODE_ENV stripped by _validate_env_vars() so it can never
    # collide with/override the fixed wiring above.
    for key, value in (env_vars or {}).items():
        argv += ["-e", f"{key}={value}"]
    argv.append(settings.NEXTJS_RUNTIME_IMAGE)

    minimal_env = {"PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")}

    logger.info(
        "nextjs_runtime_start deployment_id=%s container=%s env_var_count=%s mode=direct",
        deployment_id, name, len(env_vars or {}),
    )

    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, check=False, env=minimal_env,
        )
    except FileNotFoundError:
        raise RuntimeError_(
            "Next.js runtime environment is not available on this deployment. Contact your platform operator."
        ) from None

    log_lines = [proc.stdout.strip(), proc.stderr.strip()] if (proc.stdout or proc.stderr) else []
    log_lines = [l for l in log_lines if l]

    if proc.returncode != 0:
        _stop_runtime_direct(name)
        raise RuntimeError_("Runtime container failed to start. See logs for details.", log_lines=log_lines)

    deadline = time.monotonic() + settings.NEXTJS_HEALTH_STARTUP_TIMEOUT_SECONDS
    last_code: Optional[int] = None
    attempts = 0
    while time.monotonic() < deadline and attempts < settings.NEXTJS_HEALTH_RETRY_COUNT:
        attempts += 1
        if not _is_running_direct(name):
            _stop_runtime_direct(name)
            raise RuntimeError_("Runtime container exited before becoming healthy.", log_lines=log_lines)
        ip = _container_ip(name, settings.NEXTJS_RUNTIME_NETWORK)
        if ip:
            ok, last_code = _probe_health(
                f"http://{ip}:{port}/", settings.NEXTJS_HEALTH_REQUEST_TIMEOUT_SECONDS
            )
            if ok:
                logger.info(
                    "nextjs_runtime_healthy deployment_id=%s container=%s status_code=%s",
                    deployment_id, name, last_code,
                )
                return RuntimeStartResult(container_name=name, healthy=True, status_code=last_code, log_lines=log_lines)
        time.sleep(settings.NEXTJS_HEALTH_RETRY_INTERVAL_SECONDS)

    _stop_runtime_direct(name)
    raise RuntimeError_(
        "Runtime container failed its health check within the startup timeout.",
        log_lines=log_lines,
    )


# ---- orchestrator mode (production — see orchestrator/README.md) ----------


def _start_runtime_via_orchestrator(
    *, artifact_dir: Path, deployment_id: UUID, env_vars: Optional[Dict[str, str]] = None
) -> RuntimeStartResult:
    """POST to build-orchestrator's /v1/nextjs-runtimes. artifact_dir is only
    used to derive workspace_id/site_id/artifact_id from its own path
    structure (<STATIC_SITES_DIR>/<workspace_id>/<site_id>/<artifact_id>) —
    the orchestrator recomputes the real host path itself from those UUIDs,
    exactly like nextjs_build.py / vite_build.py never trust a path string
    from this process."""
    import httpx

    parts = Path(artifact_dir).resolve().parts
    workspace_id, site_id, artifact_id = parts[-3], parts[-2], parts[-1]

    url = settings.VITE_BUILD_ORCHESTRATOR_URL.rstrip("/") + "/v1/nextjs-runtimes"
    payload = {
        "workspace_id": workspace_id,
        "site_id": site_id,
        "artifact_id": artifact_id,
        "deployment_id": str(deployment_id),
        # Full server-side environment for THIS container only — re-
        # validated (reserved keys stripped) by the orchestrator itself too.
        "env_vars": env_vars or {},
    }
    headers = {"Authorization": f"Bearer {settings.VITE_BUILD_ORCHESTRATOR_SHARED_SECRET}"}

    logger.info(
        "nextjs_runtime_start deployment_id=%s env_var_count=%s mode=orchestrator",
        deployment_id, len(env_vars or {}),
    )

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=settings.NEXTJS_HEALTH_STARTUP_TIMEOUT_SECONDS + 15)
    except httpx.TimeoutException:
        raise RuntimeError_("Runtime startup exceeded the allowed time limit.") from None
    except httpx.HTTPError:
        raise RuntimeError_(
            "Next.js runtime environment is not available on this deployment. Contact your platform operator."
        ) from None

    if resp.status_code != 200:
        raise RuntimeError_("Runtime container failed to start. See logs for details.")

    body = resp.json()
    log_lines = list(body.get("log_lines") or [])
    if not body.get("success") or not body.get("healthy"):
        raise RuntimeError_(
            str(body.get("error") or "Runtime container failed its health check."), log_lines=log_lines
        )

    return RuntimeStartResult(
        container_name=str(body.get("container_name")),
        healthy=True,
        status_code=body.get("status_code"),
        log_lines=log_lines,
    )


def _stop_runtime_via_orchestrator(name: str) -> None:
    import httpx

    url = settings.VITE_BUILD_ORCHESTRATOR_URL.rstrip("/") + f"/v1/nextjs-runtimes/{name}"
    headers = {"Authorization": f"Bearer {settings.VITE_BUILD_ORCHESTRATOR_SHARED_SECRET}"}
    try:
        httpx.delete(url, headers=headers, timeout=30)
    except httpx.HTTPError:
        logger.warning("nextjs_runtime_stop_failed container=%s", name)


def _is_running_via_orchestrator(name: str) -> bool:
    import httpx

    url = settings.VITE_BUILD_ORCHESTRATOR_URL.rstrip("/") + f"/v1/nextjs-runtimes/{name}"
    headers = {"Authorization": f"Bearer {settings.VITE_BUILD_ORCHESTRATOR_SHARED_SECRET}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
    except httpx.HTTPError:
        return False
    if resp.status_code != 200:
        return False
    return bool(resp.json().get("running"))
