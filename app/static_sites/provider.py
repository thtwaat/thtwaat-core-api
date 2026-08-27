"""StaticSiteProvider — extract/publish an uploaded static site.

Deliberately NOT app.studio.deploy.VpsDockerProvider: it must never run
`docker compose`, never run npm/build tooling, never execute uploaded code,
and never rebuild or restart the production stack. It only ever (1) moves
already-validated bytes into an isolated directory, and (2) reuses the
existing Domain Manager + SSL Manager to point nginx at that directory.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.static_sites.nextjs_build import NextjsBuildError, run_nextjs_build
from app.static_sites.vite_build import BuildError, run_vite_build
from app.static_sites.vite_detect import ProjectFramework, detect_project_framework
from app.storage.safe_extract import UnsafeArchiveError, safe_extract_zip

logger = logging.getLogger(__name__)

STAGES = (
    "queued",
    "validating",
    "detecting",
    "preparing_build",
    "installing_dependencies",
    "building",
    "validating_output",
    "extracting",
    "publishing",
    "domain",
    "ssl",
    "health_check",
    "completed",
    "failed",
    "rollback",
)


class StaticDeployError(Exception):
    """A pipeline-stage failure with a message safe to show to the tenant."""

    def __init__(self, message: str, *, log_lines: Optional[List[str]] = None):
        super().__init__(message)
        self.log_lines = log_lines or []


StageCallback = Callable[[str, str], None]


def static_site_root() -> Path:
    root = Path(getattr(settings, "STATIC_SITES_DIR", "data/static-sites"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def deployment_directory(workspace_id: UUID, site_id: UUID, deployment_id: UUID) -> Path:
    """Isolated, immutable directory for one deployment version.

    Every path segment is a server-generated UUID (workspace/site/deployment
    id) — never the uploaded filename, the site name, or a hostname.
    """
    root = static_site_root().resolve()
    return root / str(workspace_id) / str(site_id) / str(deployment_id)


def preview_deployment_directory(
    workspace_id: UUID, site_id: UUID, preview_id: UUID, generation: int
) -> Path:
    """THTWAAT Deploy Phase 6A — isolated, immutable directory for ONE
    generation of one preview. A distinct filesystem sub-namespace
    (.../previews/...) from deployment_directory()'s production tree —
    structurally impossible to collide with a production deployment_id's
    directory, and makes bulk preview cleanup/inspection trivial. Every path
    segment is still a server-generated UUID/int — never derived from PR
    title, branch name, or any other user-influenced string."""
    root = static_site_root().resolve()
    return root / str(workspace_id) / str(site_id) / "previews" / str(preview_id) / str(int(generation))


def staging_directory(deployment_id: UUID) -> Path:
    """Scratch extraction root for a zip that needs inspection (framework
    detection / build) before its final immutable content is known — never
    itself served by nginx (only deployment_directory() ever is), always
    removed after prepare_deployment() finishes (success or failure)."""
    return static_site_root().resolve() / "_staging" / str(deployment_id)


_FLATTEN_DEFAULT_MARKERS = ("index.html",)


def _flatten_single_root_dir(extract_dir: Path, markers: tuple = _FLATTEN_DEFAULT_MARKERS) -> None:
    """If the zip's only top-level entry is a directory (a common `Export as
    ZIP` shape) and none of `markers` is at the root, hoist that directory's
    contents up one level so e.g. index.html or package.json lands where
    expected."""
    if any((extract_dir / m).exists() for m in markers):
        return
    entries = list(extract_dir.iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        return
    inner = entries[0]
    if not any((inner / m).exists() for m in markers):
        return
    for child in list(inner.iterdir()):
        target = extract_dir / child.name
        shutil.move(str(child), str(target))
    inner.rmdir()


def extract_upload(
    *,
    upload_path: Path,
    source_type: str,
    dest_dir: Path,
) -> Dict[str, Any]:
    """Place a plain static upload into dest_dir. Raises StaticDeployError on
    any safety violation or missing index.html — never partially publishes.
    Only used for the "html" case and for the "zip" case once it has already
    been classified as static (no package.json) — see prepare_deployment().
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    if source_type == "html":
        size = upload_path.stat().st_size
        max_bytes = int(getattr(settings, "STATIC_SITE_MAX_FILE_BYTES", 20 * 1024 * 1024))
        if size > max_bytes:
            raise StaticDeployError(f"index.html too large ({size} bytes > {max_bytes} limit)")
        shutil.copyfile(upload_path, dest_dir / "index.html")
        return {"file_count": 1, "total_bytes": size}

    if source_type == "zip":
        try:
            result = safe_extract_zip(
                upload_path,
                dest_dir,
                max_archive_bytes=int(getattr(settings, "STATIC_SITE_MAX_ARCHIVE_BYTES", 50 * 1024 * 1024)),
                max_extracted_bytes=int(getattr(settings, "STATIC_SITE_MAX_EXTRACTED_BYTES", 200 * 1024 * 1024)),
                max_file_bytes=int(getattr(settings, "STATIC_SITE_MAX_FILE_BYTES", 20 * 1024 * 1024)),
                max_file_count=int(getattr(settings, "STATIC_SITE_MAX_FILE_COUNT", 5000)),
            )
        except UnsafeArchiveError as exc:
            # Sanitized, safe message only — never a stack trace or host path.
            raise StaticDeployError(f"Archive rejected: {exc}") from exc

        _flatten_single_root_dir(dest_dir)
        if not (dest_dir / "index.html").is_file():
            raise StaticDeployError("index.html was not found.")
        return {"file_count": result.file_count, "total_bytes": result.total_bytes}

    raise StaticDeployError(f"Unsupported source type: {source_type!r}")


def prepare_deployment(
    *,
    upload_path: Path,
    source_type: str,
    dest_dir: Path,
    deployment_id: UUID,
    workspace_id: UUID,
    site_id: UUID,
    stage_callback: Optional[StageCallback] = None,
    resolved_env_vars: Optional[List["ResolvedEnvVar"]] = None,
) -> Dict[str, Any]:
    """Extract, detect, and (if Vite) build an upload into its final,
    immutable dest_dir. Reuses safe_extract_zip unchanged; adds framework
    detection and — only for Vite — an isolated `docker run` build between
    extraction and publish. dest_dir ends up holding ONLY the final static
    content (dist/ for Vite, the extracted tree for plain static) in every
    case; the raw source (package.json, src/, any node_modules a build
    produced) never becomes part of the published, nginx-served directory.

    resolved_env_vars (Phase 4B): this deployment's already-decrypted
    immutable environment-variable snapshot (see
    app/static_sites/env_resolver.py::resolve_deployment_env_vars) — split
    here by framework-specific public/private rules right before dispatching
    to the Vite/Next.js build, since the framework isn't known until
    detect_project_framework() runs a few lines below. A plain static
    HTML/ZIP deployment never uses this at all.

    Returns {file_count, total_bytes, framework, warnings, build_log}.
    Raises StaticDeployError on any handled failure (unsupported framework,
    bad archive, missing entry point, build failure).
    """
    from app.static_sites.env_resolver import nextjs_public_build_vars, vite_client_vars

    resolved_env_vars = resolved_env_vars or []
    if source_type == "html":
        info = extract_upload(upload_path=upload_path, source_type="html", dest_dir=dest_dir)
        return {**info, "framework": ProjectFramework.STATIC_HTML.value, "warnings": [], "build_log": []}

    if source_type != "zip":
        raise StaticDeployError(f"Unsupported source type: {source_type!r}")

    staging_dir = staging_directory(deployment_id)
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    def _emit(stage: str, message: str) -> None:
        if stage_callback:
            stage_callback(stage, message)

    try:
        try:
            extract_result = safe_extract_zip(
                upload_path,
                staging_dir,
                max_archive_bytes=int(getattr(settings, "STATIC_SITE_MAX_ARCHIVE_BYTES", 50 * 1024 * 1024)),
                max_extracted_bytes=int(getattr(settings, "STATIC_SITE_MAX_EXTRACTED_BYTES", 200 * 1024 * 1024)),
                max_file_bytes=int(getattr(settings, "STATIC_SITE_MAX_FILE_BYTES", 20 * 1024 * 1024)),
                max_file_count=int(getattr(settings, "STATIC_SITE_MAX_FILE_COUNT", 5000)),
            )
        except UnsafeArchiveError as exc:
            raise StaticDeployError(f"Archive rejected: {exc}") from exc

        _flatten_single_root_dir(staging_dir, markers=("index.html", "package.json"))

        _emit("detecting", "Detecting project type")
        detection = detect_project_framework(staging_dir)

        if detection.framework == ProjectFramework.UNSUPPORTED:
            raise StaticDeployError(detection.message)

        if detection.framework == ProjectFramework.VITE:
            for w in detection.warnings:
                _emit("detecting", w)
            _emit("preparing_build", "Preparing isolated Vite build")
            _emit("installing_dependencies", f"Installing dependencies (npm {'ci' if detection.use_ci else 'install'})")
            _emit("building", "Running npm run build in an isolated sandbox")
            try:
                build_result = run_vite_build(
                    source_dir=staging_dir,
                    dest_dir=dest_dir,
                    deployment_id=deployment_id,
                    workspace_id=workspace_id,
                    site_id=site_id,
                    use_ci=detection.use_ci,
                    client_env_vars=vite_client_vars(resolved_env_vars),
                )
            except BuildError as exc:
                raise StaticDeployError(str(exc), log_lines=exc.log_lines) from exc
            _emit("validating_output", "Validating build output")
            return {
                "file_count": build_result.file_count,
                "total_bytes": build_result.total_bytes,
                "framework": ProjectFramework.VITE.value,
                "warnings": detection.warnings,
                "build_log": build_result.log_lines,
            }

        if detection.framework == ProjectFramework.NEXTJS:
            for w in detection.warnings:
                _emit("detecting", w)
            _emit("preparing_build", "Preparing isolated Next.js build")
            _emit("installing_dependencies", f"Installing dependencies (npm {'ci' if detection.use_ci else 'install'})")
            _emit("building", "Running npm run build in an isolated sandbox")
            try:
                nextjs_result = run_nextjs_build(
                    source_dir=staging_dir,
                    dest_dir=dest_dir,
                    deployment_id=deployment_id,
                    workspace_id=workspace_id,
                    site_id=site_id,
                    use_ci=detection.use_ci,
                    public_env_vars=nextjs_public_build_vars(resolved_env_vars),
                )
            except NextjsBuildError as exc:
                raise StaticDeployError(str(exc), log_lines=exc.log_lines) from exc
            _emit("validating_output", "Validating standalone build output")
            return {
                "file_count": nextjs_result.file_count,
                "total_bytes": nextjs_result.total_bytes,
                "framework": ProjectFramework.NEXTJS.value,
                "warnings": detection.warnings,
                "build_log": nextjs_result.log_lines,
            }

        # STATIC_ZIP — no package.json, or package.json present but not
        # Vite/Next.js (already rejected above as UNSUPPORTED); plain static
        # content.
        if not (staging_dir / "index.html").is_file():
            raise StaticDeployError("index.html was not found.")
        dest_dir.mkdir(parents=True, exist_ok=True)
        for child in list(staging_dir.iterdir()):
            shutil.move(str(child), str(dest_dir / child.name))
        return {
            "file_count": extract_result.file_count,
            "total_bytes": extract_result.total_bytes,
            "framework": ProjectFramework.STATIC_ZIP.value,
            "warnings": [],
            "build_log": [],
        }
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


@dataclass
class StaticDeployContext:
    site_id: UUID
    deployment_id: UUID
    workspace_id: UUID
    site_name: str
    version: int
    db_session: Session
    actor_user_id: Optional[UUID] = None


def bind_hostname_and_ssl(
    ctx: StaticDeployContext,
    progress,
    *,
    hostname: str,
    mode: str,
    dns_validated: bool,
    deployment_dir: Optional[Path] = None,
    runtime_target: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve domain + SSL via the EXISTING Domain Manager / SSL Manager,
    then point the vhost at this deployment's directory OR runtime
    container. No second domain or SSL engine — this is a thin wrapper
    around app.studio.deploy's own bind_free_subdomain()/bind_domain_and_ssl()
    plus one extra call so the generated vhost serves files (static
    deployments, deployment_dir given) or proxies to a runtime container
    (Next.js deployments, runtime_target given — see nginx_gen.py
    RUNTIME_PROXY_LOCATION_BLOCK) instead of the default api_backend proxy.

    Exactly one of deployment_dir/runtime_target should be given; this is
    the seam THTWAAT Phase 3 extends without touching the static path.
    """
    from app.studio.deploy import DeployContext, bind_domain_and_ssl, bind_free_subdomain

    # bind_free_subdomain()/bind_domain_and_ssl() only read
    # workspace_id/actor_user_id/db_session off this dataclass — the rest of
    # its fields are Studio/Docker-specific and unused by those two
    # functions, so placeholder values are safe here.
    deploy_ctx = DeployContext(
        project_id=ctx.site_id,
        deployment_id=ctx.deployment_id,
        workspace_id=ctx.workspace_id,
        project_title=ctx.site_name,
        provider="static",
        build_id=ctx.deployment_id,
        build_version=ctx.version,
        artifact_path=deployment_dir or Path("."),
        artifact_sha256=None,
        domain=hostname if mode == "custom" else None,
        subdomain=hostname if mode == "free_subdomain" else None,
        domain_mode=mode,
        db_session=ctx.db_session,
        actor_user_id=ctx.actor_user_id,
    )

    if mode == "free_subdomain":
        ssl_info = bind_free_subdomain(deploy_ctx, progress, hostname=hostname, dns_validated=dns_validated)
    else:
        ssl_info = bind_domain_and_ssl(deploy_ctx, progress, hostname=hostname, dns_validated=dns_validated)

    if not hostname:
        return ssl_info

    try:
        from app.domains.service import DomainService
        from app.ssl.manager import SslManager

        domain_row = DomainService(ctx.db_session).repo.get_by_hostname(hostname)
        if domain_row is not None:
            actor = ctx.actor_user_id or ctx.workspace_id
            if runtime_target:
                SslManager(ctx.db_session).set_runtime_proxy_target(
                    domain_row.id, ctx.workspace_id, runtime_target, actor
                )
            else:
                SslManager(ctx.db_session).set_static_root(
                    domain_row.id, ctx.workspace_id, str(deployment_dir), actor
                )
            ssl_info["domain_id"] = str(domain_row.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "vhost_bind_failed hostname=%s deployment_id=%s err=%s",
            hostname, ctx.deployment_id, exc,
        )
        ssl_info.setdefault("note", "")
        ssl_info["note"] = (ssl_info.get("note") or "") + " (vhost binding pending retry)"

    return ssl_info
