"""THTWAAT Deploy — isolated Next.js standalone build orchestration.

Sibling to app/static_sites/vite_build.py — same threat model, same dual
orchestrator/direct dispatch, same locked-down `docker run` shape (argv
lists, never shell=True). The only real differences: a dedicated
NEXTJS_BUILD_IMAGE (see docker/next-build/), higher default resource limits
(Next.js builds are heavier than Vite's), and output validation that checks
for the standalone runtime artifact (server.js + .next/static + public/)
instead of a plain dist/index.html.

Uploaded source is UNTRUSTED. This module never runs `npm install` / `npm
run build` on the api/worker host — see the module docstring in
vite_build.py for the full orchestrator-mode vs. direct-mode rationale,
which applies identically here.
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

# THTWAAT Deploy Phase 4B — only this prefix may ever be injected as a
# CLIENT-visible build variable. Enforced here too, not just by the caller.
_NEXTJS_PUBLIC_PREFIX = "NEXT_PUBLIC_"
_MAX_ENV_VARS = 100

logger = logging.getLogger(__name__)

_SECRET_LIKE = re.compile(r"(?i)\b(authorization|token|secret|password|api[_-]?key)\b\s*[:=]\s*.*")
_MAX_LOG_LINE_CHARS = 2000

# Defense in depth on top of build.sh only ever assembling server.js +
# .next/static + public/ from .next/standalone — never publish these even if
# a build container's output mistakenly contains them.
_FORBIDDEN_OUTPUT_NAMES = {
    ".git", ".gitignore", ".env", ".env.local", ".env.production",
    ".npmrc", "src", "yarn.lock", "pnpm-lock.yaml",
}

STANDALONE_REQUIRED_MESSAGE = "Next.js standalone output is required for this deployment."


class NextjsBuildError(Exception):
    """A build-stage failure with a message safe to show to the tenant."""

    def __init__(self, message: str, *, log_lines: Optional[List[str]] = None):
        super().__init__(message)
        self.log_lines = log_lines or []


@dataclass
class NextjsBuildResult:
    artifact_dir: Path
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


def _validate_output(dest_dir: Path, log_lines: List[str]) -> tuple[int, int]:
    if not (dest_dir / "server.js").is_file():
        raise NextjsBuildError(STANDALONE_REQUIRED_MESSAGE, log_lines=log_lines)
    if not (dest_dir / ".next" / "static").is_dir():
        raise NextjsBuildError(STANDALONE_REQUIRED_MESSAGE, log_lines=log_lines)

    present_forbidden = sorted(
        p.name for p in dest_dir.iterdir() if p.name in _FORBIDDEN_OUTPUT_NAMES
    )
    if present_forbidden:
        raise NextjsBuildError(
            f"Build output contained unexpected files: {', '.join(present_forbidden)}.",
            log_lines=log_lines,
        )

    file_count, total_bytes = _dir_stats(dest_dir)
    if file_count > settings.NEXTJS_MAX_OUTPUT_FILE_COUNT:
        raise NextjsBuildError("Build output exceeded the allowed file count.", log_lines=log_lines)
    if total_bytes > settings.NEXTJS_MAX_OUTPUT_BYTES:
        raise NextjsBuildError("Build output exceeded the allowed size limit.", log_lines=log_lines)
    return file_count, total_bytes


def _filter_public_build_env_vars(env_vars: Optional[Dict[str, str]]) -> Dict[str, str]:
    """THTWAAT Deploy Phase 4B — defense in depth: only NEXT_PUBLIC_*-
    prefixed keys ever reach a Next.js build container as client-visible
    build vars, no matter what the caller passed in."""
    if not env_vars:
        return {}
    filtered = {k: v for k, v in env_vars.items() if k.startswith(_NEXTJS_PUBLIC_PREFIX)}
    if len(filtered) > _MAX_ENV_VARS:
        raise NextjsBuildError(f"Too many environment variables for this build (max {_MAX_ENV_VARS}).")
    return filtered


def run_nextjs_build(
    *,
    source_dir: Path,
    dest_dir: Path,
    deployment_id: uuid.UUID,
    workspace_id: uuid.UUID,
    site_id: uuid.UUID,
    use_ci: bool,
    public_env_vars: Optional[Dict[str, str]] = None,
) -> NextjsBuildResult:
    """Build an already-extracted, already-detected Next.js project.

    dest_dir must already exist and be empty (the caller's isolated,
    server-generated deployment directory — see deployment_directory()).
    Raises NextjsBuildError on any failure; log_lines are always attached so
    the caller can persist them regardless of outcome. Dispatches to
    orchestrator or direct mode exactly like run_vite_build().

    public_env_vars (Phase 4B): NEXT_PUBLIC_*-prefixed key/value pairs only
    — inlined into the client bundle at build time. Server-only secrets are
    never passed here; they reach the app via nextjs_runtime.py's runtime
    injection instead. Re-filtered here regardless of what the caller did.
    """
    if not getattr(settings, "NEXTJS_BUILD_ENABLED", False):
        raise NextjsBuildError(
            "Next.js builds are not enabled on this deployment. Contact your platform operator."
        )

    install_cmd = "ci" if use_ci else "install"
    filtered_env_vars = _filter_public_build_env_vars(public_env_vars)

    if getattr(settings, "VITE_BUILD_ORCHESTRATOR_URL", ""):
        return _run_nextjs_build_via_orchestrator(
            dest_dir=dest_dir,
            deployment_id=deployment_id,
            workspace_id=workspace_id,
            site_id=site_id,
            install_cmd=install_cmd,
            env_vars=filtered_env_vars,
        )
    return _run_nextjs_build_direct(
        source_dir=source_dir, dest_dir=dest_dir, deployment_id=deployment_id, install_cmd=install_cmd,
        env_vars=filtered_env_vars,
    )


def _run_nextjs_build_via_orchestrator(
    *,
    dest_dir: Path,
    deployment_id: uuid.UUID,
    workspace_id: uuid.UUID,
    site_id: uuid.UUID,
    install_cmd: str,
    env_vars: Optional[Dict[str, str]] = None,
) -> NextjsBuildResult:
    """POST the build request to build-orchestrator and wait for the result.

    Reuses the SAME orchestrator service/URL/shared-secret as Vite builds
    (settings.VITE_BUILD_ORCHESTRATOR_URL/_SHARED_SECRET) — it is one
    narrow-schema control-plane process with a second endpoint added
    (/v1/nextjs-builds), not a second service. See orchestrator/README.md.
    """
    import httpx

    url = settings.VITE_BUILD_ORCHESTRATOR_URL.rstrip("/") + "/v1/nextjs-builds"
    payload = {
        "workspace_id": str(workspace_id),
        "site_id": str(site_id),
        "deployment_id": str(deployment_id),
        "install_cmd": install_cmd,
        # NEXT_PUBLIC_*-only key/value pairs — re-validated by the
        # orchestrator itself before injection. Never logged here or there.
        "env_vars": env_vars or {},
    }
    headers = {"Authorization": f"Bearer {settings.VITE_BUILD_ORCHESTRATOR_SHARED_SECRET}"}

    logger.info(
        "nextjs_build_start deployment_id=%s install_cmd=%s env_var_count=%s mode=orchestrator",
        deployment_id, install_cmd, len(env_vars or {}),
    )

    start = time.perf_counter()
    try:
        resp = httpx.post(
            url, json=payload, headers=headers,
            timeout=settings.VITE_BUILD_ORCHESTRATOR_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        raise NextjsBuildError("Build exceeded the allowed resource limit.") from None
    except httpx.HTTPError:
        raise NextjsBuildError(
            "Next.js build environment is not available on this deployment. Contact your platform operator."
        ) from None

    if resp.status_code != 200:
        raise NextjsBuildError("Build failed. See logs for details.")

    body = resp.json()
    log_lines = list(body.get("log_lines") or [])
    if not body.get("success"):
        raise NextjsBuildError(str(body.get("error") or "Build failed. See logs for details."), log_lines=log_lines)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "nextjs_build_complete deployment_id=%s duration_ms=%s mode=orchestrator",
        deployment_id, duration_ms,
    )
    return NextjsBuildResult(
        artifact_dir=dest_dir,
        file_count=int(body.get("file_count") or 0),
        total_bytes=int(body.get("total_bytes") or 0),
        log_lines=log_lines,
        duration_ms=int(body.get("duration_ms") or duration_ms),
    )


def _run_nextjs_build_direct(
    *,
    source_dir: Path,
    dest_dir: Path,
    deployment_id: uuid.UUID,
    install_cmd: str,
    env_vars: Optional[Dict[str, str]] = None,
) -> NextjsBuildResult:
    """Shell out to `docker` directly from this process (local/dev only —
    see vite_build.py's _run_vite_build_direct docstring for the identical
    rationale; docker-compose.prod.yml never grants api/worker Docker socket
    access, they always go through the orchestrator in production)."""
    container_name = f"thtwaat-nextjs-build-{deployment_id.hex}"
    source_dir = Path(source_dir).resolve()
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(dest_dir, 0o777)
    except OSError:
        logger.warning("nextjs_build_chmod_failed dest_dir=%s", dest_dir)

    argv = [
        "docker", "run",
        "--rm",
        "--name", container_name,
        "--network", settings.NEXTJS_BUILD_NETWORK,
        "--memory", f"{settings.NEXTJS_MAX_BUILD_MEMORY_MB}m",
        "--memory-swap", f"{settings.NEXTJS_MAX_BUILD_MEMORY_MB}m",
        "--cpus", str(settings.NEXTJS_MAX_BUILD_CPU),
        "--pids-limit", "256",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "1000:1000",
        "--tmpfs", f"/tmp:rw,size={settings.NEXTJS_BUILD_TMPFS_MB}m,mode=1777",
        "-v", f"{source_dir}:/workspace/source:ro",
        "-v", f"{dest_dir}:/workspace/output:rw",
        "-e", f"INSTALL_CMD={install_cmd}",
        "-e", "NODE_ENV=production",
        "-e", "CI=true",
        "-e", "NPM_CONFIG_FUND=false",
        "-e", "NPM_CONFIG_AUDIT=false",
        "-e", f"MAX_NODE_MODULES_BYTES={int(settings.NEXTJS_MAX_NODE_MODULES_BYTES)}",
    ]
    # THTWAAT Deploy Phase 4B — NEXT_PUBLIC_*-only client build vars.
    for key, value in (env_vars or {}).items():
        argv += ["-e", f"{key}={value}"]
    argv.append(settings.NEXTJS_BUILD_IMAGE)

    logger.info(
        "nextjs_build_start deployment_id=%s install_cmd=%s network=%s env_var_count=%s mode=direct",
        deployment_id, install_cmd, settings.NEXTJS_BUILD_NETWORK, len(env_vars or {}),
    )

    minimal_env = {"PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")}

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.NEXTJS_MAX_BUILD_TIME_SECONDS,
            check=False,
            env=minimal_env,
        )
    except subprocess.TimeoutExpired as exc:
        _kill_container(container_name)
        log_lines = _capture_log(
            exc.stdout.decode() if isinstance(exc.stdout, (bytes, bytearray)) else (exc.stdout or ""),
            exc.stderr.decode() if isinstance(exc.stderr, (bytes, bytearray)) else (exc.stderr or ""),
            settings.NEXTJS_MAX_LOG_BYTES,
        )
        raise NextjsBuildError("Build exceeded the allowed resource limit.", log_lines=log_lines) from None
    except FileNotFoundError:
        raise NextjsBuildError(
            "Next.js build environment is not available on this deployment. Contact your platform operator."
        ) from None

    duration_ms = int((time.perf_counter() - start) * 1000)
    log_lines = _capture_log(proc.stdout, proc.stderr, settings.NEXTJS_MAX_LOG_BYTES)

    if proc.returncode != 0:
        # build.sh already writes STANDALONE_REQUIRED_MESSAGE to stderr when
        # .next/standalone is missing — surface that exact line if present so
        # the tenant sees the Phase 3-mandated message, not a generic one.
        for line in reversed(log_lines):
            if STANDALONE_REQUIRED_MESSAGE in line:
                raise NextjsBuildError(STANDALONE_REQUIRED_MESSAGE, log_lines=log_lines)
        raise NextjsBuildError("Build failed. See logs for details.", log_lines=log_lines)

    file_count, total_bytes = _validate_output(dest_dir, log_lines)

    logger.info(
        "nextjs_build_complete deployment_id=%s duration_ms=%s files=%s bytes=%s mode=direct",
        deployment_id, duration_ms, file_count, total_bytes,
    )
    return NextjsBuildResult(
        artifact_dir=dest_dir, file_count=file_count, total_bytes=total_bytes,
        log_lines=log_lines, duration_ms=duration_ms,
    )
