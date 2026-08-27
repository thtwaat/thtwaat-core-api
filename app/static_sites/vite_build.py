"""THTWAAT Deploy — isolated Vite build orchestration (Phases 2-7, 17).

Uploaded source is UNTRUSTED. This module never runs `npm install` / `npm
run build` on the api/worker host. It only ever constructs and runs a single
`docker run` invocation against the dedicated, locked-down VITE_BUILD_IMAGE
(see docker/vite-build/), using argv lists (never shell=True, never string
interpolation of anything user-controlled into a shell command), and reads
back only the produced `dist/` directory.

Two ways that `docker run` invocation actually happens, selected by whether
settings.VITE_BUILD_ORCHESTRATOR_URL is set:

  - Orchestrator mode (recommended production posture — see
    orchestrator/README.md and the Phase 2 staging validation report §1):
    this process (api/worker) never touches Docker at all. It POSTs
    {workspace_id, site_id, deployment_id, install_cmd} to the dedicated
    build-orchestrator service, which is the only process anywhere in the
    stack with Docker socket (or docker-socket-proxy) access, and which
    recomputes every filesystem path itself from those UUIDs rather than
    trusting a path string from this process.
  - Direct mode (local/dev only — docker-compose.yml, never
    docker-compose.prod.yml): this process shells out to `docker` itself,
    which requires it to have Docker socket access. Kept for simplicity in
    single-host dev setups; see _run_vite_build_direct()'s docstring.

Either way, the build container itself:
  - runs as a fixed non-root uid:gid
  - has no capabilities (--cap-drop=ALL), no privilege escalation
  - has a hard memory/CPU/pids cap
  - is attached to a dedicated network, never the network carrying
    Postgres/Redis/the internal API/nginx management
  - never receives the Docker socket, host filesystem, SSH keys, SSL
    private keys, or database credentials — its only inputs are the
    extracted source (read-only bind mount) and a fixed, validated
    INSTALL_CMD value ("ci" or "install"); its only output channel is the
    output directory (read-write bind mount)
  - is killed and removed on timeout or on any failure
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.config.settings import settings

# THTWAAT Deploy Phase 4B — only this prefix may ever be injected into a
# Vite build. Enforced here too (not just by the caller) — this module never
# trusts that env_vars passed in have already been filtered.
_VITE_PUBLIC_PREFIX = "VITE_"
_MAX_ENV_VARS = 100

logger = logging.getLogger(__name__)

_SECRET_LIKE = re.compile(r"(?i)\b(authorization|token|secret|password|api[_-]?key)\b\s*[:=]\s*.*")
_MAX_LOG_LINE_CHARS = 2000

# Never publish these even if a build container's dist/ mistakenly contains
# them — defense in depth on top of build.sh only ever copying dist/.
_FORBIDDEN_OUTPUT_NAMES = {
    "node_modules", ".git", ".gitignore", "package.json", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "src",
}


class BuildError(Exception):
    """A build-stage failure with a message safe to show to the tenant."""

    def __init__(self, message: str, *, log_lines: Optional[List[str]] = None):
        super().__init__(message)
        self.log_lines = log_lines or []


@dataclass
class BuildResult:
    dist_dir: Path
    file_count: int
    total_bytes: int
    log_lines: List[str] = field(default_factory=list)
    duration_ms: int = 0


def _sanitize_log_line(line: str) -> str:
    line = line[:_MAX_LOG_LINE_CHARS]
    return _SECRET_LIKE.sub(lambda m: m.group(0).split(":")[0].split("=")[0] + "=****", line)


def _capture_log(stdout: str, stderr: str, max_bytes: int) -> List[str]:
    lines: List[str] = []
    total = 0
    for raw in (stdout or "").splitlines() + (["--- stderr ---"] if stderr else []) + (stderr or "").splitlines():
        sanitized = _sanitize_log_line(raw)
        total += len(sanitized) + 1
        if total > max_bytes:
            lines.append("… (log truncated)")
            break
        lines.append(sanitized)
    return lines


def _kill_container(name: str) -> None:
    for cmd in (["docker", "kill", name], ["docker", "rm", "-f", name]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=15, check=False)
        except Exception:  # noqa: BLE001
            pass


def _dir_stats(root: Path) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            file_count += 1
            try:
                total_bytes += (Path(dirpath) / name).stat().st_size
            except OSError:
                pass
    return file_count, total_bytes


def _filter_client_env_vars(env_vars: Optional[Dict[str, str]]) -> Dict[str, str]:
    """THTWAAT Deploy Phase 4B — defense in depth: only VITE_*-prefixed keys
    ever reach a Vite build container, no matter what the caller passed in.
    Silently drops anything else rather than injecting it — a dropped
    server-only var here is a caller bug upstream (env_resolver.py should
    never have included it), not a reason to fail the whole build."""
    if not env_vars:
        return {}
    filtered = {k: v for k, v in env_vars.items() if k.startswith(_VITE_PUBLIC_PREFIX)}
    if len(filtered) > _MAX_ENV_VARS:
        raise BuildError(f"Too many environment variables for this build (max {_MAX_ENV_VARS}).")
    return filtered


def run_vite_build(
    *,
    source_dir: Path,
    dest_dir: Path,
    deployment_id: uuid.UUID,
    workspace_id: uuid.UUID,
    site_id: uuid.UUID,
    use_ci: bool,
    client_env_vars: Optional[Dict[str, str]] = None,
) -> BuildResult:
    """Build an already-extracted, already-detected Vite project.

    dest_dir must already exist and be empty (the caller's isolated,
    server-generated deployment directory — see deployment_directory()).
    Raises BuildError on any failure; log_lines are always attached so the
    caller can persist them regardless of outcome. Dispatches to
    orchestrator or direct mode — see module docstring.

    client_env_vars (Phase 4B): VITE_*-prefixed key/value pairs resolved from
    this deployment's immutable environment-variable snapshot (see
    app/static_sites/env_resolver.py) — never a server-only secret. Re-
    filtered here regardless of what the caller already did.
    """
    if not getattr(settings, "VITE_BUILD_ENABLED", False):
        raise BuildError(
            "Vite builds are not enabled on this deployment. Contact your platform operator."
        )

    install_cmd = "ci" if use_ci else "install"
    filtered_env_vars = _filter_client_env_vars(client_env_vars)

    if getattr(settings, "VITE_BUILD_ORCHESTRATOR_URL", ""):
        return _run_vite_build_via_orchestrator(
            dest_dir=dest_dir,
            deployment_id=deployment_id,
            workspace_id=workspace_id,
            site_id=site_id,
            install_cmd=install_cmd,
            env_vars=filtered_env_vars,
        )
    return _run_vite_build_direct(
        source_dir=source_dir, dest_dir=dest_dir, deployment_id=deployment_id, install_cmd=install_cmd,
        env_vars=filtered_env_vars,
    )


def _run_vite_build_via_orchestrator(
    *,
    dest_dir: Path,
    deployment_id: uuid.UUID,
    workspace_id: uuid.UUID,
    site_id: uuid.UUID,
    install_cmd: str,
    env_vars: Optional[Dict[str, str]] = None,
) -> BuildResult:
    """POST the build request to build-orchestrator and wait for the result.

    Deliberately sends only the three UUIDs + install_cmd — never a path,
    image name, or docker argument (see orchestrator/app/main.py, which
    recomputes source_dir/dest_dir itself from these same UUIDs against its
    own STATIC_SITES_DIR; this process's dest_dir Path is only used below to
    read back the result, since api/worker and build-orchestrator share the
    same host directory via an identical bind mount).
    """
    import httpx

    url = settings.VITE_BUILD_ORCHESTRATOR_URL.rstrip("/") + "/v1/vite-builds"
    payload = {
        "workspace_id": str(workspace_id),
        "site_id": str(site_id),
        "deployment_id": str(deployment_id),
        "install_cmd": install_cmd,
        # VITE_*-only key/value pairs — re-validated by the orchestrator
        # itself before injection (never trusts this process's filtering
        # alone). Never logged here or by the orchestrator.
        "env_vars": env_vars or {},
    }
    headers = {"Authorization": f"Bearer {settings.VITE_BUILD_ORCHESTRATOR_SHARED_SECRET}"}

    logger.info(
        "vite_build_start deployment_id=%s install_cmd=%s env_var_count=%s mode=orchestrator",
        deployment_id, install_cmd, len(env_vars or {}),
    )

    start = time.perf_counter()
    try:
        resp = httpx.post(
            url, json=payload, headers=headers,
            timeout=settings.VITE_BUILD_ORCHESTRATOR_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        raise BuildError("Build exceeded the allowed resource limit.") from None
    except httpx.HTTPError:
        raise BuildError(
            "Vite build environment is not available on this deployment. Contact your platform operator."
        ) from None

    if resp.status_code != 200:
        raise BuildError("Build failed. See logs for details.")

    body = resp.json()
    log_lines = list(body.get("log_lines") or [])
    if not body.get("success"):
        raise BuildError(str(body.get("error") or "Build failed. See logs for details."), log_lines=log_lines)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "vite_build_complete deployment_id=%s duration_ms=%s mode=orchestrator",
        deployment_id, duration_ms,
    )
    return BuildResult(
        dist_dir=dest_dir,
        file_count=int(body.get("file_count") or 0),
        total_bytes=int(body.get("total_bytes") or 0),
        log_lines=log_lines,
        duration_ms=int(body.get("duration_ms") or duration_ms),
    )


def _run_vite_build_direct(
    *,
    source_dir: Path,
    dest_dir: Path,
    deployment_id: uuid.UUID,
    install_cmd: str,
    env_vars: Optional[Dict[str, str]] = None,
) -> BuildResult:
    """Shell out to `docker` directly from this process.

    Local/dev fallback only (docker-compose.yml) — requires this process to
    have Docker socket access, which docker-compose.prod.yml deliberately
    never grants api/worker (see the orchestrator mode above and the Phase 2
    staging validation report §1). Kept, rather than removed, because it is
    the exact invocation this validation report exercised live end-to-end;
    ripping it out would be a larger, unvalidated change than hardening
    production's actual path via the orchestrator instead.
    """
    container_name = f"thtwaat-vite-build-{deployment_id.hex}"
    source_dir = Path(source_dir).resolve()
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    # The caller (api/worker) runs as root; the build container writes
    # as a fixed non-root uid:gid (1000:1000, matching the image's built-in
    # `node` user). Without this, the bind-mounted output dir is root-owned mode
    # 0755 and the container's `cp dist/. /workspace/output/` step fails
    # with permission denied. os.chmod (not os.chown) so this stays portable
    # to non-POSIX dev environments where this function is merely imported.
    try:
        os.chmod(dest_dir, 0o777)
    except OSError:
        logger.warning("vite_build_chmod_failed dest_dir=%s", dest_dir)

    argv = [
        "docker", "run",
        "--rm",
        "--name", container_name,
        "--network", settings.VITE_BUILD_NETWORK,
        "--memory", f"{settings.VITE_MAX_BUILD_MEMORY_MB}m",
        "--memory-swap", f"{settings.VITE_MAX_BUILD_MEMORY_MB}m",  # swap disabled
        "--cpus", str(settings.VITE_MAX_BUILD_CPU),
        "--pids-limit", "256",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "1000:1000",
        "--tmpfs", f"/tmp:rw,size={settings.VITE_BUILD_TMPFS_MB}m,mode=1777",
        "-v", f"{source_dir}:/workspace/source:ro",
        "-v", f"{dest_dir}:/workspace/output:rw",
        "-e", f"INSTALL_CMD={install_cmd}",
        "-e", "NODE_ENV=production",
        "-e", "CI=true",
        "-e", "NPM_CONFIG_FUND=false",
        "-e", "NPM_CONFIG_AUDIT=false",
        "-e", f"MAX_NODE_MODULES_BYTES={int(settings.VITE_MAX_NODE_MODULES_BYTES)}",
    ]
    # THTWAAT Deploy Phase 4B — VITE_*-only client vars, appended as
    # additional `-e KEY=VALUE` argv entries (never string-interpolated into
    # a shell command — this whole invocation is argv-list based already).
    for key, value in (env_vars or {}).items():
        argv += ["-e", f"{key}={value}"]
    argv.append(settings.VITE_BUILD_IMAGE)

    logger.info(
        "vite_build_start deployment_id=%s install_cmd=%s network=%s env_var_count=%s mode=direct",
        deployment_id, install_cmd, settings.VITE_BUILD_NETWORK, len(env_vars or {}),
    )

    # `docker run -e KEY=VALUE` (used exclusively above) never forwards the
    # calling process's own environment into the container — only the fixed
    # KEY=VALUE pairs listed in argv. This minimal env is extra defense in
    # depth for the `docker` CLI *client* process itself: the api/worker
    # container's own DB/JWT/webhook secrets (injected via its env_file) are
    # deliberately not visible to it, in case docker ever echoed its own
    # environment into logs/crash output.
    minimal_env = {"PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")}

    start = time.perf_counter()
    try:
        # Pin encoding — the container's stdout (npm/vite) is always UTF-8;
        # without this, text=True decodes with the host's locale encoding,
        # which can mangle non-ASCII log output (checkmarks, box-drawing).
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.VITE_MAX_BUILD_TIME_SECONDS,
            check=False,
            env=minimal_env,
        )
    except subprocess.TimeoutExpired as exc:
        _kill_container(container_name)
        log_lines = _capture_log(
            exc.stdout.decode() if isinstance(exc.stdout, (bytes, bytearray)) else (exc.stdout or ""),
            exc.stderr.decode() if isinstance(exc.stderr, (bytes, bytearray)) else (exc.stderr or ""),
            settings.VITE_MAX_LOG_BYTES,
        )
        raise BuildError("Build exceeded the allowed resource limit.", log_lines=log_lines) from None
    except FileNotFoundError:
        raise BuildError(
            "Vite build environment is not available on this deployment. Contact your platform operator."
        ) from None

    duration_ms = int((time.perf_counter() - start) * 1000)
    log_lines = _capture_log(proc.stdout, proc.stderr, settings.VITE_MAX_LOG_BYTES)

    if proc.returncode != 0:
        raise BuildError("Build failed. See logs for details.", log_lines=log_lines)

    if not (dest_dir / "index.html").is_file():
        raise BuildError("Build succeeded but dist/index.html was not found.", log_lines=log_lines)

    present_forbidden = sorted(
        p.name for p in dest_dir.iterdir() if p.name in _FORBIDDEN_OUTPUT_NAMES
    )
    if present_forbidden:
        raise BuildError(
            f"Build output contained unexpected files: {', '.join(present_forbidden)}.",
            log_lines=log_lines,
        )

    file_count, total_bytes = _dir_stats(dest_dir)
    if file_count > settings.VITE_MAX_OUTPUT_FILE_COUNT:
        raise BuildError("Build output exceeded the allowed file count.", log_lines=log_lines)
    if total_bytes > settings.VITE_MAX_OUTPUT_BYTES:
        raise BuildError("Build output exceeded the allowed size limit.", log_lines=log_lines)

    logger.info(
        "vite_build_complete deployment_id=%s duration_ms=%s files=%s bytes=%s mode=direct",
        deployment_id, duration_ms, file_count, total_bytes,
    )
    return BuildResult(
        dist_dir=dest_dir, file_count=file_count, total_bytes=total_bytes,
        log_lines=log_lines, duration_ms=duration_ms,
    )
