"""The actual `docker run` invocation for the Vite build sandbox.

Deliberately self-contained (not imported from app.static_sites.vite_build):
this process is a separate, minimal deployable unit by design (see
orchestrator/README.md) and must not gain a dependency on the main
application package, which would pull SQLAlchemy/DB models/JWT code into a
service that should never touch any of that. Some duplication with
app/static_sites/vite_build.py's direct-mode fallback is the accepted cost
of that isolation — both implement the same fixed, locked-down `docker run`
invocation; changes to the sandboxed flags must be mirrored in both places
(see the comment block in vite_build.py's direct-mode function).

Callers (main.py) supply only workspace_id/site_id/deployment_id/install_cmd
— every filesystem path used below is computed here from those validated
UUIDs, never accepted as a string from the caller. That is the actual
security boundary of this service: even a fully compromised api/worker
process can only ever ask this service to build "the thing already staged
under this deployment_id", never an arbitrary host path, image, or command.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from orchestrator_app.settings import settings

logger = logging.getLogger(__name__)

_SECRET_LIKE = re.compile(r"(?i)\b(authorization|token|secret|password|api[_-]?key)\b\s*[:=]\s*.*")
_FORBIDDEN_OUTPUT_NAMES = {
    "node_modules", ".git", ".gitignore", "package.json", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "src",
}


class BuildError(Exception):
    def __init__(self, message: str, *, log_lines: Optional[List[str]] = None):
        super().__init__(message)
        self.log_lines = log_lines or []


@dataclass
class BuildResult:
    file_count: int
    total_bytes: int
    log_lines: List[str] = field(default_factory=list)
    duration_ms: int = 0


def _sanitize_log_line(line: str) -> str:
    line = line[:2000]
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


def _kill_container(name: str, docker_env: dict) -> None:
    for cmd in (["docker", "kill", name], ["docker", "rm", "-f", name]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=15, check=False, env=docker_env)
        except Exception:  # noqa: BLE001
            pass


def _host_path(container_path: Path) -> str:
    """Translate this container's own view of STATIC_SITES_DIR into the
    literal host path the same directory is bind-mounted from — required
    because the *host* Docker daemon (reached via socket/socket-proxy)
    resolves `-v` bind-mount sources against the host filesystem, not
    against this container's filesystem namespace. Mirrors
    app/ssl/nginx_gen.py's _remap_static_root() for the identical problem."""
    internal_root = Path(settings.STATIC_SITES_DIR).resolve()
    rel = container_path.resolve().relative_to(internal_root)
    return str(Path(settings.STATIC_SITES_HOST_DIR) / rel).replace("\\", "/")


def run_build(
    *,
    workspace_id: UUID,
    site_id: UUID,
    deployment_id: UUID,
    install_cmd: str,
    env_vars: Optional[Dict[str, str]] = None,
) -> BuildResult:
    if install_cmd not in ("ci", "install"):
        raise BuildError("Unsupported install_cmd")
    # Defense in depth — main.py's BuildRequest validator already enforces
    # this, but this function never trusts a caller upstream alone.
    env_vars = {k: v for k, v in (env_vars or {}).items() if k.startswith("VITE_")}

    root = Path(settings.STATIC_SITES_DIR).resolve()
    source_dir = root / "_staging" / str(deployment_id)
    dest_dir = root / str(workspace_id) / str(site_id) / str(deployment_id)

    if not source_dir.is_dir():
        raise BuildError("Staged source directory does not exist")

    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(dest_dir, 0o777)
    except OSError:
        logger.warning("orchestrator_chmod_failed dest_dir=%s", dest_dir)

    container_name = f"thtwaat-vite-build-{deployment_id.hex}"
    argv = [
        "docker", "run",
        "--rm",
        "--name", container_name,
        "--network", settings.VITE_BUILD_NETWORK,
        "--memory", f"{settings.VITE_MAX_BUILD_MEMORY_MB}m",
        "--memory-swap", f"{settings.VITE_MAX_BUILD_MEMORY_MB}m",
        "--cpus", str(settings.VITE_MAX_BUILD_CPU),
        "--pids-limit", "256",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "1000:1000",
        "--tmpfs", f"/tmp:rw,size={settings.VITE_BUILD_TMPFS_MB}m,mode=1777",
        "-v", f"{_host_path(source_dir)}:/workspace/source:ro",
        "-v", f"{_host_path(dest_dir)}:/workspace/output:rw",
        "-e", f"INSTALL_CMD={install_cmd}",
        "-e", "NODE_ENV=production",
        "-e", "CI=true",
        "-e", "NPM_CONFIG_FUND=false",
        "-e", "NPM_CONFIG_AUDIT=false",
        "-e", f"MAX_NODE_MODULES_BYTES={int(settings.VITE_MAX_NODE_MODULES_BYTES)}",
    ]
    if settings.VITE_BUILD_EGRESS_PROXY_URL:
        argv += [
            "-e", f"HTTP_PROXY={settings.VITE_BUILD_EGRESS_PROXY_URL}",
            "-e", f"HTTPS_PROXY={settings.VITE_BUILD_EGRESS_PROXY_URL}",
        ]
    for key, value in env_vars.items():
        argv += ["-e", f"{key}={value}"]
    argv.append(settings.VITE_BUILD_IMAGE)

    docker_env = {"PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")}
    if settings.DOCKER_HOST:
        docker_env["DOCKER_HOST"] = settings.DOCKER_HOST

    logger.info(
        "orchestrator_build_start deployment_id=%s install_cmd=%s env_var_count=%s",
        deployment_id, install_cmd, len(env_vars),
    )

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.VITE_MAX_BUILD_TIME_SECONDS,
            check=False,
            env=docker_env,
        )
    except subprocess.TimeoutExpired as exc:
        _kill_container(container_name, docker_env)
        log_lines = _capture_log(
            exc.stdout.decode() if isinstance(exc.stdout, (bytes, bytearray)) else (exc.stdout or ""),
            exc.stderr.decode() if isinstance(exc.stderr, (bytes, bytearray)) else (exc.stderr or ""),
            settings.VITE_MAX_LOG_BYTES,
        )
        raise BuildError("Build exceeded the allowed resource limit.", log_lines=log_lines) from None
    except FileNotFoundError:
        raise BuildError("Docker is not available to the build orchestrator.") from None

    duration_ms = int((time.perf_counter() - start) * 1000)
    log_lines = _capture_log(proc.stdout, proc.stderr, settings.VITE_MAX_LOG_BYTES)

    if proc.returncode != 0:
        raise BuildError("Build failed. See logs for details.", log_lines=log_lines)

    if not (dest_dir / "index.html").is_file():
        raise BuildError("Build succeeded but dist/index.html was not found.", log_lines=log_lines)

    present_forbidden = sorted(p.name for p in dest_dir.iterdir() if p.name in _FORBIDDEN_OUTPUT_NAMES)
    if present_forbidden:
        raise BuildError(
            f"Build output contained unexpected files: {', '.join(present_forbidden)}.", log_lines=log_lines
        )

    file_count, total_bytes = _dir_stats(dest_dir)
    if file_count > settings.VITE_MAX_OUTPUT_FILE_COUNT:
        raise BuildError("Build output exceeded the allowed file count.", log_lines=log_lines)
    if total_bytes > settings.VITE_MAX_OUTPUT_BYTES:
        raise BuildError("Build output exceeded the allowed size limit.", log_lines=log_lines)

    logger.info(
        "orchestrator_build_complete deployment_id=%s duration_ms=%s files=%s bytes=%s",
        deployment_id, duration_ms, file_count, total_bytes,
    )
    return BuildResult(file_count=file_count, total_bytes=total_bytes, log_lines=log_lines, duration_ms=duration_ms)
