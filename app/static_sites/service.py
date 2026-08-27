"""StaticSiteService — THTWAAT Deploy orchestration.

Auth/company-scoping/RBAC conventions are copied verbatim from
app/studio/service.py (StudioService.get() / _require_deploy_manager()) —
Step 6 of this feature explicitly reuses that convention rather than
inventing a third authorization mechanism.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schema import UserProfileResponse
from app.auth.tenant import can_manage_company_users
from app.config.settings import settings
from app.static_sites import github_client, nextjs_runtime
from app.static_sites.env_redaction import build_secret_redactor, redact_lines
from app.static_sites.env_resolver import (
    EnvVarResolutionError,
    clone_env_var_snapshot,
    nextjs_server_runtime_vars,
    resolve_deployment_env_vars,
    secret_values,
    snapshot_env_vars,
)
from app.static_sites.models import GitHubConnection, StaticSite, StaticSiteDeployment
from app.static_sites.provider import (
    StaticDeployContext,
    StaticDeployError,
    bind_hostname_and_ssl,
    deployment_directory,
    prepare_deployment,
    static_site_root,
)
from app.static_sites.repository import StaticSiteRepository
from app.static_sites.schemas import (
    StaticSiteCreateRequest,
    StaticSiteDeploymentListResponse,
    StaticSiteDeploymentResponse,
    StaticSiteListResponse,
    StaticSiteResponse,
    StaticSiteRollbackRequest,
)

logger = logging.getLogger(__name__)

# Never persist/return these — sanitize any internal error into one of these
# generic, safe messages before writing to deployment.error / logs.
_GENERIC_FAILURE_MESSAGE = "Deployment failed due to an internal error. Our team has been notified."


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "site").lower()).strip("-")
    return (cleaned[:48] or "site")


class StaticSiteService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StaticSiteRepository(db)

    # ---- auth helpers (mirrors app/studio/service.py exactly) -----------

    def _require_deploy_manager(self, user: UserProfileResponse) -> None:
        if not can_manage_company_users(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company owners and admins can deploy or rollback",
            )

    def _get_site(self, user: UserProfileResponse, site_id: UUID) -> StaticSite:
        site = self.repo.get_site_for_workspace(site_id, UUID(str(user.company_id)))
        if not site:
            raise HTTPException(status_code=404, detail="Static site not found")
        return site

    def _audit(self, *, company_id: UUID, actor_id: Optional[UUID], action: str, resource_id: str, metadata: Optional[dict] = None) -> None:
        try:
            from app.enterprise.models import AuditSeverity
            from app.enterprise.service import EnterpriseService

            EnterpriseService(self.db).audit(
                company_id,
                actor_id,
                action=action,
                resource_type="static_site_deployment",
                resource_id=resource_id,
                severity=AuditSeverity.INFO,
                metadata=metadata or {},
                commit=True,
            )
        except Exception:  # noqa: BLE001
            logger.warning("static_deploy_audit_failed action=%s", action)

    def _emit(self, deployment_id: UUID, stage: str, **data: Any) -> None:
        try:
            from app.studio.deploy_events import publish_deploy_event

            publish_deploy_event(deployment_id, stage, {"stage": stage, **data})
        except Exception:  # noqa: BLE001
            logger.debug("static_deploy_event_publish_failed stage=%s", stage)

    # ---- sites ------------------------------------------------------------

    def create_site(self, user: UserProfileResponse, payload: StaticSiteCreateRequest) -> StaticSiteResponse:
        self._require_deploy_manager(user)
        workspace_id = UUID(str(user.company_id))
        base_slug = _slugify(payload.name)
        slug = base_slug
        n = 2
        while self.repo.get_site_by_slug(workspace_id, slug) is not None:
            slug = f"{base_slug}-{n}"
            n += 1

        site = StaticSite(
            workspace_id=workspace_id,
            user_id=UUID(str(user.id)) if getattr(user, "id", None) else None,
            name=payload.name.strip(),
            slug=slug,
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        site = self.repo.create_site(site)
        return StaticSiteResponse.model_validate(site)

    def list_sites(self, user: UserProfileResponse, limit: int = 50, offset: int = 0) -> StaticSiteListResponse:
        workspace_id = UUID(str(user.company_id))
        items = self.repo.list_sites(workspace_id, limit=limit, offset=offset)
        return StaticSiteListResponse(
            items=[StaticSiteResponse.model_validate(i) for i in items], total=len(items)
        )

    def get_site(self, user: UserProfileResponse, site_id: UUID) -> StaticSiteResponse:
        return StaticSiteResponse.model_validate(self._get_site(user, site_id))

    # ---- deploy -------------------------------------------------------------

    def deploy_upload(
        self,
        user: UserProfileResponse,
        site_id: UUID,
        *,
        upload_path: Path,
        source_type: str,
        original_filename: str,
        upload_size_bytes: int,
        domain_mode: str = "free_subdomain",
        custom_domain: Optional[str] = None,
        environment: str = "production",
        idempotency_key: Optional[str] = None,
    ) -> StaticSiteDeploymentResponse:
        self._require_deploy_manager(user)
        site = self._get_site(user, site_id)

        mode = (domain_mode or "free_subdomain").strip().lower().replace("-", "_")
        if mode not in {"free_subdomain", "custom"}:
            mode = "free_subdomain"
        custom_domain = (custom_domain or "").strip().lower() or None
        if mode == "custom" and not custom_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A domain is required when domain_mode='custom'",
            )

        idempotency_key = (idempotency_key or "").strip()[:200] or None
        if idempotency_key:
            # Fast path: an earlier call with this exact key already ran (or
            # is running) the pipeline — never launch a second Docker build
            # for a retried/duplicated request (Phase 2 staging validation
            # report §12). Deliberately checked BEFORE clear_current_deployments()
            # below so a duplicate request never perturbs is_current either.
            existing = self.repo.get_idempotent_deployment(site.id, idempotency_key)
            if existing is not None:
                try:
                    upload_path.unlink(missing_ok=True)
                except Exception:  # noqa: BLE001
                    pass
                return StaticSiteDeploymentResponse.model_validate(existing)

        self.repo.clear_current_deployments(site.id)
        version = self.repo.next_deployment_version(site.id)

        row = StaticSiteDeployment(
            site_id=site.id,
            workspace_id=site.workspace_id,
            version=version,
            is_current=True,
            provider="static",
            status="queued",
            stage="queued",
            source_type=source_type,
            upload_filename=original_filename,
            upload_size_bytes=upload_size_bytes,
            environment=environment or "production",
            live=False,
            urls={},
            health={},
            ssl={},
            instructions=[],
            logs=[{"stage": "queued", "message": "Deployment accepted"}],
            created_by=UUID(str(user.id)) if getattr(user, "id", None) else None,
        )
        row = self.repo.create_deployment(row)

        if idempotency_key:
            claimed = self.repo.claim_idempotency_key(site.id, idempotency_key, row.id)
            if not claimed:
                # Lost a genuine race to a concurrent request using the same
                # key — row's pipeline never started, safe to discard. The
                # winner is whatever the other request's row is.
                self.repo.delete_deployment(row.id)
                winner = self.repo.get_idempotent_deployment(site.id, idempotency_key)
                try:
                    upload_path.unlink(missing_ok=True)
                except Exception:  # noqa: BLE001
                    pass
                if winner is not None:
                    return StaticSiteDeploymentResponse.model_validate(winner)
                # Extremely unlikely (winner's own row was deleted between
                # our failed claim and this lookup) — fall through and treat
                # this request as if it had no idempotency key rather than
                # erroring a legitimate upload over a bookkeeping race.

        self._emit(row.id, "queued", message="Deployment accepted")

        try:
            self._run_pipeline(
                user=user,
                site=site,
                row=row,
                upload_path=upload_path,
                source_type=source_type,
                mode=mode,
                custom_domain=custom_domain,
            )
        finally:
            try:
                upload_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass

        return StaticSiteDeploymentResponse.model_validate(row)

    def _stop_runtime_safely(self, container_name: Optional[str]) -> None:
        if not container_name:
            return
        try:
            nextjs_runtime.stop_runtime(container_name)
        except Exception:  # noqa: BLE001
            logger.warning("nextjs_runtime_stop_failed container=%s", container_name)

    def _mark_if_superseded(
        self,
        row: StaticSiteDeployment,
        current_now: Optional[StaticSiteDeployment],
        *,
        start: Optional[float] = None,
    ) -> bool:
        """Returns True (and marks row completed-but-inactive) if
        current_now is a DIFFERENT, HIGHER-version deployment for the same
        site — see the call sites in _run_pipeline() and run_github_deploy()
        for why this check exists. row.is_current is set to False
        explicitly here rather than trusted from whatever was loaded into
        memory: the newer deployment's own creation already flipped it at
        the DB level (StaticSiteRepository.clear_current_deployments is a
        bulk UPDATE, which does not refresh this row's in-memory state)."""
        if current_now is None or current_now.id == row.id:
            return False
        try:
            is_newer = current_now.version > row.version
        except TypeError:
            # Defensive only — a real StaticSiteDeployment.version is always
            # an int; this guards a caller that passed something else
            # (e.g. an unconfigured test double) rather than ever treating
            # that as "superseded".
            return False
        if not is_newer:
            return False
        row.is_current = False
        row.status = "completed"
        row.stage = "completed"
        row.live = False
        if start is not None:
            row.duration_ms = int((time.perf_counter() - start) * 1000)
        row.logs = list(row.logs or []) + [
            {
                "stage": "completed",
                "message": (
                    f"Superseded by a newer deployment (v{current_now.version}); "
                    "not activated."
                ),
            }
        ]
        self.repo.save_deployment(row)
        self._emit(row.id, "completed", message="Superseded by a newer deployment", live=False, superseded=True)
        return True

    def _fail(self, row: StaticSiteDeployment, *, stage: str, safe_message: str, dest_dir: Optional[Path] = None) -> None:
        # deploy_upload()/rollback() already set row.is_current=True on
        # creation, before the pipeline outcome is known — a failed row must
        # give that back to whichever deployment is still actually serving
        # traffic, or get_current_deployment()/is_current in API responses
        # would point at the failed attempt instead of the live version.
        # A Next.js row can fail AFTER its runtime container already started
        # and passed its health check (e.g. a later DB write or domain-bind
        # exception) — never leave that container running unaccounted for.
        self._stop_runtime_safely(row.runtime_container_id)
        row.is_current = False
        row.status = "failed"
        row.stage = "failed"
        row.error = safe_message
        row.live = False
        row.health_status = "stopped" if row.runtime_container_id else row.health_status
        row.logs = list(row.logs or []) + [{"stage": stage, "message": safe_message}]
        self.repo.save_deployment(row)
        previous = self.repo.find_previous_completed(row.site_id, row.workspace_id, exclude_id=row.id)
        if previous is not None:
            previous.is_current = True
            self.repo.save_deployment(previous)
        self._emit(row.id, "failed", message=safe_message)
        if dest_dir is not None:
            shutil.rmtree(dest_dir, ignore_errors=True)

    def fail_deployment(self, row: StaticSiteDeployment, *, safe_message: str) -> None:
        """Public wrapper around _fail() for callers outside this class that
        need to mark an already-created deployment row failed without going
        through the full upload/rollback/run_github_deploy pipeline — e.g.
        github_webhook_router.py when enqueueing the async job itself fails
        after create_github_deployment() already committed the row."""
        self._fail(row, stage=row.stage or "queued", safe_message=safe_message)

    def _run_pipeline(
        self,
        *,
        user: Optional[UserProfileResponse],
        site: StaticSite,
        row: StaticSiteDeployment,
        upload_path: Path,
        source_type: str,
        mode: str,
        custom_domain: Optional[str],
    ) -> None:
        from app.studio.deploy import probe_http
        from app.studio.domain_validation import resolve_deploy_hostname

        start = time.perf_counter()
        dest_dir: Optional[Path] = None
        try:
            dest_dir = deployment_directory(site.workspace_id, site.id, row.id)

            # THTWAAT Deploy Phase 4B — snapshot THEN resolve, before any
            # build/runtime container starts (spec §10/§16): a later edit to
            # the site's live env vars must never change what this
            # deployment uses, and a var that fails to decrypt must fail the
            # whole deployment cleanly rather than starting a build with a
            # partial set.
            try:
                snapshot_env_vars(
                    self.repo,
                    deployment_id=row.id,
                    workspace_id=site.workspace_id,
                    site_id=site.id,
                    environment=row.environment,
                )
                resolved_env_vars = resolve_deployment_env_vars(self.repo, deployment_id=row.id)
            except EnvVarResolutionError as exc:
                self._fail(row, stage="env_resolution", safe_message=str(exc), dest_dir=dest_dir)
                return
            redact = build_secret_redactor(secret_values(resolved_env_vars))

            row.status = "validating"
            row.stage = "validating"
            self.repo.save_deployment(row)
            self._emit(row.id, "validating", message="Validating uploaded source")

            row.stage = "extracting"
            self.repo.save_deployment(row)
            self._emit(row.id, "extracting", message="Extracting deployment")

            def _on_prepare_stage(stage: str, message: str) -> None:
                # Called synchronously from prepare_deployment() for the
                # detect/build sub-stages (Vite only) — persists progress so
                # the SSE stream and deployment-history UI show real stages
                # (detecting → preparing_build → installing_dependencies →
                # building → validating_output) instead of one opaque
                # "extracting" step for the whole build duration.
                row.stage = stage
                self.repo.save_deployment(row)
                self._emit(row.id, stage, message=message)

            try:
                extract_info = prepare_deployment(
                    upload_path=upload_path, source_type=source_type, dest_dir=dest_dir,
                    deployment_id=row.id, workspace_id=site.workspace_id, site_id=site.id,
                    stage_callback=_on_prepare_stage,
                    resolved_env_vars=resolved_env_vars,
                )
            except StaticDeployError as exc:
                row.logs = list(row.logs or []) + [
                    {"stage": "building", "message": line} for line in redact_lines(exc.log_lines or [], redact)
                ]
                self._fail(row, stage=row.stage or "extracting", safe_message=str(exc), dest_dir=dest_dir)
                return

            row.deployment_path = str(dest_dir)
            row.file_count = int(extract_info.get("file_count") or 0)
            row.total_bytes = int(extract_info.get("total_bytes") or 0)
            row.framework = str(extract_info.get("framework") or "static_zip")
            row.stage = "publishing"
            row.logs = list(row.logs or []) + [
                {"stage": "extracting", "message": f"Extracted {row.file_count} file(s) (framework: {row.framework})"}
            ] + [
                {"stage": "building", "message": line}
                for line in redact_lines(extract_info.get("build_log") or [], redact)
            ] + [
                {"stage": "detecting", "message": w}
                for w in redact_lines(extract_info.get("warnings") or [], redact)
            ]
            self.repo.save_deployment(row)

            # THTWAAT Deploy Phase 5C — stale-commit / concurrency guard
            # (spec §13): if a higher-version deployment has already become
            # this site's current one while THIS row was still building
            # (e.g. two GitHub pushes landed close together and their jobs
            # overlapped), this row must never activate over it — no
            # runtime container, no nginx switch, no is_current flip. It
            # still finishes "completed" (the build itself succeeded) so it
            # remains a valid rollback target; it's just never served.
            current_now = self.repo.get_current_deployment(row.site_id, row.workspace_id)
            if self._mark_if_superseded(row, current_now, start=start):
                return

            runtime_target: Optional[str] = None
            previous_nextjs: Optional[StaticSiteDeployment] = None
            if row.framework == "nextjs":
                # Zero-downtime cutover (Phase 11): the previously-completed
                # version (if any) is captured now, before we touch nginx or
                # start anything new — its runtime container is left running
                # and untouched until AFTER the new version passes its
                # health check and nginx has switched to it, below.
                previous_nextjs = self.repo.find_previous_completed(
                    row.site_id, row.workspace_id, exclude_id=row.id
                )
                # THTWAAT Deploy Phase 6A — combined with live PREVIEW
                # runtimes too (count_live_preview_nextjs_runtimes), so a
                # company can't bypass this cap by opening preview
                # deployments instead of production ones.
                live_count = self.repo.count_live_nextjs_runtimes(
                    row.workspace_id
                ) + self.repo.count_live_preview_nextjs_runtimes(row.workspace_id)
                if live_count >= settings.NEXTJS_MAX_RUNTIMES_PER_COMPANY:
                    self._fail(
                        row, stage="publishing",
                        safe_message=(
                            f"This company has reached its limit of {settings.NEXTJS_MAX_RUNTIMES_PER_COMPANY} "
                            "live Next.js deployments. Stop or remove one before deploying another."
                        ),
                        dest_dir=dest_dir,
                    )
                    return

                row.stage = "runtime_starting"
                self.repo.save_deployment(row)
                self._emit(row.id, "runtime_starting", message="Starting isolated Next.js runtime")
                try:
                    runtime_result = nextjs_runtime.start_runtime(
                        artifact_dir=dest_dir,
                        deployment_id=row.id,
                        server_env_vars=nextjs_server_runtime_vars(resolved_env_vars),
                    )
                except nextjs_runtime.RuntimeError_ as exc:
                    row.logs = list(row.logs or []) + [
                        {"stage": "runtime_starting", "message": line}
                        for line in redact_lines(exc.log_lines or [], redact)
                    ]
                    self._fail(row, stage="runtime_starting", safe_message=str(exc), dest_dir=dest_dir)
                    return

                row.runtime_type = "node"
                row.runtime_container_id = runtime_result.container_name
                row.internal_port = int(settings.NEXTJS_RUNTIME_PORT)
                row.health_status = "healthy" if runtime_result.healthy else "unhealthy"
                row.logs = list(row.logs or []) + [
                    {"stage": "runtime_starting", "message": line}
                    for line in redact_lines(runtime_result.log_lines or [], redact)
                ] + [{"stage": "runtime_starting", "message": "Runtime container passed health check"}]
                self.repo.save_deployment(row)
                self._emit(row.id, "runtime_starting", message="Runtime healthy", container=row.runtime_container_id)
                runtime_target = nextjs_runtime.proxy_target(runtime_result.container_name)

            self._emit(row.id, "publishing", message="Publishing deployment")

            hostname, resolved_mode, validation = resolve_deploy_hostname(
                domain_mode=mode,
                custom_domain=custom_domain,
                project_id=site.id,
                project_title=site.name,
            )

            row.stage = "domain"
            if resolved_mode == "free_subdomain":
                row.subdomain = hostname
                row.domain = None
            else:
                row.domain = hostname
                row.subdomain = None
            self.repo.save_deployment(row)
            self._emit(row.id, "domain", message=f"Assigning hostname {hostname}")

            ctx = StaticDeployContext(
                site_id=site.id,
                deployment_id=row.id,
                workspace_id=site.workspace_id,
                site_name=site.name,
                version=row.version,
                db_session=self.db,
                actor_user_id=UUID(str(user.id)) if getattr(user, "id", None) else None,
            )

            row.stage = "ssl"
            self.repo.save_deployment(row)
            self._emit(row.id, "ssl", message="Provisioning SSL")
            try:
                ssl_info = bind_hostname_and_ssl(
                    ctx, self._emit_progress, hostname=hostname, mode=resolved_mode,
                    dns_validated=bool(validation.reachable),
                    deployment_dir=None if runtime_target else dest_dir,
                    runtime_target=runtime_target,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "static_deploy_domain_bind_failed deployment_id=%s hostname=%s", row.id, hostname
                )
                ssl_info = {"status": "error", "ssl_enabled": False, "ssl_status": "PENDING"}

            row.ssl = {k: v for k, v in ssl_info.items() if k != "error"}
            self.repo.save_deployment(row)

            ssl_val = str(ssl_info.get("ssl_status") or "").upper()
            row.stage = "health_check"
            self.repo.save_deployment(row)
            self._emit(row.id, "health_check", message="Checking deployed site health")

            health: Dict[str, Any] = {}
            live = False
            if ssl_val in {"ACTIVE", "ISSUED"}:
                health = probe_http(f"https://{hostname}/")
                live = bool(health.get("ok"))
                row.status = "completed"
                row.stage = "completed"
            else:
                row.status = "provisioning_ssl"
                row.stage = "ssl"

            row.health = health
            row.live = live
            row.urls = {"website": f"https://{hostname}"} if hostname else {}
            row.duration_ms = int((time.perf_counter() - start) * 1000)
            row.logs = list(row.logs or []) + [
                {"stage": row.stage, "message": "Deployment live" if live else "Deployment complete — waiting on DNS/SSL"}
            ]
            self.repo.save_deployment(row)
            self._emit(row.id, row.status, message="Deployment finished", live=live)

            # Zero-downtime cutover complete (Phase 11): nginx now proxies
            # this hostname to the NEW runtime container (regardless of
            # whether the probe_http() above returned ok — nginx already
            # switched once set_runtime_proxy_target() reloaded it, and the
            # new container did pass its OWN health check in start_runtime()
            # above). Only now is it safe to stop the previous version's
            # runtime — v1 stayed up and untouched for this entire pipeline.
            if runtime_target and previous_nextjs is not None and previous_nextjs.runtime_container_id:
                if previous_nextjs.runtime_container_id != row.runtime_container_id:
                    self._stop_runtime_safely(previous_nextjs.runtime_container_id)
                    previous_nextjs.health_status = "stopped"
                    self.repo.save_deployment(previous_nextjs)

            self._audit(
                company_id=site.workspace_id,
                actor_id=ctx.actor_user_id,
                action="static_deploy.create",
                resource_id=str(row.id),
                metadata={"site_id": str(site.id), "version": row.version, "hostname": hostname},
            )
        except Exception:  # noqa: BLE001
            # Catch-all safety net: anything not already handled above (the
            # deployment directory can't be created, resolve_deploy_hostname
            # raises, or a mid-pipeline DB write fails) must still mark the
            # row failed with a sanitized message instead of leaving it stuck
            # at queued/validating forever with no response reaching the
            # client and an orphaned extraction directory on disk.
            logger.exception("static_deploy_pipeline_failed deployment_id=%s", row.id)
            self._fail(row, stage=row.stage or "failed", safe_message=_GENERIC_FAILURE_MESSAGE, dest_dir=dest_dir)

    def _emit_progress(self, stage: str, payload: Dict[str, Any]) -> None:
        # Adapter for app.studio.deploy's ProgressCallback signature — we
        # already emit our own stage events; just log domain/ssl bind detail.
        logger.debug("static_deploy_domain_progress stage=%s payload=%s", stage, payload)

    # ---- history / detail --------------------------------------------------

    def list_deployments(self, user: UserProfileResponse, site_id: UUID) -> StaticSiteDeploymentListResponse:
        site = self._get_site(user, site_id)
        rows = self.repo.list_deployments(site.id, site.workspace_id)
        return StaticSiteDeploymentListResponse(
            items=[StaticSiteDeploymentResponse.model_validate(r) for r in rows], total=len(rows)
        )

    def get_deployment(self, user: UserProfileResponse, site_id: UUID, deployment_id: UUID) -> StaticSiteDeploymentResponse:
        site = self._get_site(user, site_id)
        row = self.repo.get_deployment(deployment_id)
        if not row or row.site_id != site.id or row.workspace_id != site.workspace_id:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return StaticSiteDeploymentResponse.model_validate(row)

    # ---- rollback -----------------------------------------------------------

    def rollback(
        self, user: UserProfileResponse, site_id: UUID, payload: StaticSiteRollbackRequest
    ) -> StaticSiteDeploymentResponse:
        from app.studio.deploy import probe_http

        self._require_deploy_manager(user)
        site = self._get_site(user, site_id)

        current = self.repo.get_current_deployment(site.id, site.workspace_id)
        if not current:
            raise HTTPException(status_code=400, detail="No current deployment to roll back from")

        if payload.deployment_id:
            target = self.repo.get_deployment(payload.deployment_id)
            if not target or target.site_id != site.id or target.workspace_id != site.workspace_id:
                raise HTTPException(status_code=404, detail="Deployment not found")
            if target.status != "completed":
                raise HTTPException(status_code=400, detail="Can only roll back to a completed deployment")
        else:
            target = self.repo.find_previous_completed(site.id, site.workspace_id, exclude_id=current.id)
            if not target:
                raise HTTPException(status_code=400, detail="No previous completed deployment to roll back to")

        if not target.deployment_path or not Path(target.deployment_path).is_dir():
            raise HTTPException(status_code=400, detail="Previous deployment content is no longer available")

        self.repo.clear_current_deployments(site.id)
        version = self.repo.next_deployment_version(site.id)
        actor = UUID(str(user.id)) if getattr(user, "id", None) else None

        row = StaticSiteDeployment(
            site_id=site.id,
            workspace_id=site.workspace_id,
            version=version,
            is_current=True,
            provider="static",
            status="queued",
            stage="rollback",
            source_type=target.source_type,
            framework=target.framework,
            upload_filename=target.upload_filename,
            upload_size_bytes=target.upload_size_bytes,
            deployment_path=target.deployment_path,  # same immutable directory — never re-extracted
            domain=target.domain,
            subdomain=target.subdomain,
            environment=target.environment,
            file_count=target.file_count,
            total_bytes=target.total_bytes,
            rollback_of=target.id,
            urls=dict(target.urls or {}),
            logs=[{"stage": "rollback", "message": f"Rolling back to v{target.version}"}],
            created_by=actor,
        )
        row = self.repo.create_deployment(row)
        self._emit(row.id, "rollback", message=f"Rolling back to v{target.version}")

        # THTWAAT Deploy Phase 4B — rollback restores the TARGET's own
        # immutable environment snapshot, never the site's current live env
        # vars (spec §11): cloning target.id's rows onto this new row means a
        # since-changed live value never leaks into a rolled-back deployment.
        try:
            clone_env_var_snapshot(self.repo, from_deployment_id=target.id, to_deployment_id=row.id)
            resolved_env_vars = resolve_deployment_env_vars(self.repo, deployment_id=row.id)
        except EnvVarResolutionError as exc:
            self._fail(row, stage="env_resolution", safe_message=str(exc))
            return StaticSiteDeploymentResponse.model_validate(row)
        redact = build_secret_redactor(secret_values(resolved_env_vars))

        runtime_target: Optional[str] = None
        if target.framework == "nextjs":
            try:
                # Never rebuild (Phase 12): reuse target's own still-running
                # container if it's alive; otherwise start a FRESH container
                # — named after this NEW rollback row, so it's a distinct,
                # independently stoppable container — from the same
                # immutable artifact directory target.deployment_path.
                # Either way, npm run build never runs again.
                if target.runtime_container_id and nextjs_runtime.is_running(target.runtime_container_id):
                    reused_name = target.runtime_container_id
                    row.runtime_container_id = reused_name
                    row.health_status = "healthy"
                    row.logs = list(row.logs or []) + [
                        {"stage": "rollback", "message": f"Reusing running runtime container {reused_name}"}
                    ]
                else:
                    self._emit(row.id, "runtime_starting", message="Starting isolated Next.js runtime")
                    runtime_result = nextjs_runtime.start_runtime(
                        artifact_dir=Path(target.deployment_path),
                        deployment_id=row.id,
                        server_env_vars=nextjs_server_runtime_vars(resolved_env_vars),
                    )
                    row.runtime_container_id = runtime_result.container_name
                    row.health_status = "healthy" if runtime_result.healthy else "unhealthy"
                    row.logs = list(row.logs or []) + [
                        {"stage": "runtime_starting", "message": line}
                        for line in redact_lines(runtime_result.log_lines or [], redact)
                    ] + [{"stage": "runtime_starting", "message": "Runtime container passed health check"}]
                row.runtime_type = "node"
                row.internal_port = int(settings.NEXTJS_RUNTIME_PORT)
                self.repo.save_deployment(row)
                runtime_target = nextjs_runtime.proxy_target(row.runtime_container_id)
            except nextjs_runtime.RuntimeError_ as exc:
                self._fail(row, stage="runtime_starting", safe_message=str(exc))
                return StaticSiteDeploymentResponse.model_validate(row)

        try:
            hostname = row.subdomain or row.domain
            ssl_val = ""
            try:
                from app.domains.service import DomainService
                from app.ssl.manager import SslManager

                if hostname:
                    domain_row = DomainService(self.db).repo.get_by_hostname(hostname)
                    if domain_row is not None:
                        ssl_manager = SslManager(self.db)
                        if runtime_target:
                            result = ssl_manager.set_runtime_proxy_target(
                                domain_row.id, site.workspace_id, runtime_target, actor or site.workspace_id
                            )
                        else:
                            result = ssl_manager.set_static_root(
                                domain_row.id, site.workspace_id, target.deployment_path, actor or site.workspace_id
                            )
                        row.ssl = {k: v for k, v in result.items() if k != "error"}
                        ssl_val = str(result.get("ssl_status") or "").upper()
            except Exception:  # noqa: BLE001
                logger.exception(
                    "static_rollback_ssl_repoint_failed deployment_id=%s hostname=%s", row.id, hostname
                )

            health: Dict[str, Any] = {}
            live = False
            if hostname and ssl_val in {"ACTIVE", "ISSUED"}:
                health = probe_http(f"https://{hostname}/")
                live = bool(health.get("ok"))

            row.health = health
            row.live = live
            row.status = "completed"
            row.stage = "completed"
            row.urls = {"website": f"https://{hostname}"} if hostname else {}
            row.logs = list(row.logs or []) + [{"stage": "completed", "message": "Rollback complete"}]
            self.repo.save_deployment(row)
            self._emit(row.id, "completed", message="Rollback complete", live=live)

            # Cutover to the rolled-back version is complete — only now stop
            # the runtime of the version we just rolled back FROM (`current`,
            # captured before this row existed), and only if it's a
            # different container than the one this rollback ended up using
            # (the "reuse a still-running container" path above can mean
            # they're the SAME container if rolling back to the version
            # immediately preceding a still-live one — nothing to stop then).
            if runtime_target and current.framework == "nextjs" and current.runtime_container_id:
                if current.runtime_container_id != row.runtime_container_id:
                    self._stop_runtime_safely(current.runtime_container_id)
                    current.health_status = "stopped"
                    self.repo.save_deployment(current)

            self._audit(
                company_id=site.workspace_id,
                actor_id=actor,
                action="static_deploy.rollback",
                resource_id=str(row.id),
                metadata={
                    "site_id": str(site.id), "rollback_of": str(target.id),
                    "from_version": current.version, "to_version": target.version,
                },
            )
        except Exception:  # noqa: BLE001
            # Same catch-all rationale as _run_pipeline: a rollback row was
            # already committed as "queued" above — never leave it stuck
            # there on an unexpected failure. deployment_path is deliberately
            # NOT cleaned up here (unlike a fresh deploy's dest_dir): it's the
            # older, still-immutable version's directory, still potentially
            # in use.
            logger.exception("static_deploy_rollback_failed deployment_id=%s", row.id)
            self._fail(row, stage=row.stage or "failed", safe_message=_GENERIC_FAILURE_MESSAGE)

        return StaticSiteDeploymentResponse.model_validate(row)

    # ---- THTWAAT Deploy Phase 5C — Git Push -> Auto Deploy -------------------

    def create_github_deployment(
        self,
        *,
        site: StaticSite,
        connection: GitHubConnection,
        commit_sha: str,
        branch: str,
    ) -> StaticSiteDeployment:
        """Fast path called from the webhook request itself (spec §11/§18:
        the HTTP response must return quickly — no 2-5 minute build runs
        inside this call). Only a cheap DB insert happens here, exactly
        mirroring how StudioService.deploy() creates its deployment row
        synchronously and then enqueues "studio.deploy" for the actual
        clone/build/publish work (see run_github_deploy() below, dispatched
        from scripts/worker.py's "static_site.github_deploy" job type).

        Sets is_current=True immediately, same as deploy_upload()/rollback()
        — see _mark_if_superseded() for why a later, higher-version row
        racing ahead of this one's own build is still handled safely.
        commit_sha/branch/repository identity are already validated by the
        caller (app/static_sites/github_webhook.py) before this is called;
        nothing here re-trusts anything from the raw webhook request.
        """
        self.repo.clear_current_deployments(site.id)
        version = self.repo.next_deployment_version(site.id)

        row = StaticSiteDeployment(
            site_id=site.id,
            workspace_id=site.workspace_id,
            version=version,
            is_current=True,
            provider="static",
            status="queued",
            stage="queued",
            source_type="zip",
            source_provider="github",
            github_repository_owner=connection.repository_owner,
            github_repository_name=connection.repository_name,
            github_commit_sha=commit_sha,
            github_branch=branch,
            upload_filename=None,
            upload_size_bytes=0,
            environment="production",
            live=False,
            urls={},
            health={},
            ssl={},
            instructions=[],
            logs=[
                {"stage": "queued", "message": "GitHub push received"},
                {
                    "stage": "queued",
                    "message": f"Repository verified: {connection.repository_owner}/{connection.repository_name}",
                },
                {"stage": "queued", "message": f"Commit {commit_sha[:12]} pinned"},
                {"stage": "queued", "message": "Deployment queued"},
            ],
            created_by=connection.created_by,
        )
        row = self.repo.create_deployment(row)
        self._emit(row.id, "queued", message="Deployment queued", commit_sha=commit_sha, branch=branch)
        self._audit(
            company_id=site.workspace_id,
            actor_id=connection.created_by,
            action="static_deploy.github_push",
            resource_id=str(row.id),
            metadata={
                "site_id": str(site.id),
                "repository": f"{connection.repository_owner}/{connection.repository_name}",
                "branch": branch,
                "commit_sha": commit_sha,
                "version": row.version,
            },
        )
        return row

    def run_github_deploy(self, deployment_id: UUID) -> None:
        """Worker entrypoint for job type "static_site.github_deploy" (see
        scripts/worker.py). Every value used here is re-read from the
        deployment row / GitHubConnection itself — never anything replayed
        off the original webhook HTTP request — so a job payload only ever
        needs to carry a deployment_id. Reuses _run_pipeline() UNCHANGED
        (user=None: there is no authenticated caller for a webhook-triggered
        deploy, and _run_pipeline only ever reads user.id for audit
        attribution). The one thing genuinely new here is where the bytes
        come from: fetched server-side from the connected installation's own
        short-lived token, pinned to the exact commit sha this row was
        created with (never a moving branch ref) — see
        app/static_sites/github_client.py::fetch_repository_archive.
        """
        row = self.repo.get_deployment(deployment_id)
        if row is None:
            logger.error("github_deploy_row_missing deployment_id=%s", deployment_id)
            return

        current_now = self.repo.get_current_deployment(row.site_id, row.workspace_id)
        if self._mark_if_superseded(row, current_now):
            return

        site = self.repo.get_site(row.site_id)
        if site is None:
            logger.error("github_deploy_site_missing deployment_id=%s site_id=%s", row.id, row.site_id)
            self._fail(row, stage="extracting", safe_message=_GENERIC_FAILURE_MESSAGE)
            return

        connection = self.repo.get_github_connection(site.id, site.workspace_id)
        if connection is None or not connection.repository_id or not connection.installation_id:
            self._fail(
                row, stage="extracting",
                safe_message="GitHub is no longer connected for this site.",
            )
            return

        # Carry forward whatever hostname mode the site is already serving
        # from (this is an auto-deploy — there is no request to ask a human
        # for domain_mode/custom_domain). A brand-new site with no prior
        # completed deployment defaults to a free THTWAAT subdomain, exactly
        # like the manual-upload UI's own default.
        previous = self.repo.find_previous_completed(row.site_id, row.workspace_id, exclude_id=row.id)
        if previous is not None and previous.domain:
            mode, custom_domain = "custom", previous.domain
        else:
            mode, custom_domain = "free_subdomain", None

        zip_path = static_site_root() / "_github_incoming" / f"{row.id}.zip"

        async def _fetch() -> None:
            token = await github_client.mint_installation_token(connection.installation_id)
            await github_client.fetch_repository_archive(
                token,
                connection.repository_owner,
                connection.repository_name,
                row.github_commit_sha,
                dest_path=zip_path,
            )

        try:
            try:
                asyncio.run(_fetch())
            except github_client.GitHubApiError as exc:
                self._fail(row, stage="extracting", safe_message=str(exc.detail))
                return
            except Exception:  # noqa: BLE001
                logger.exception("github_deploy_archive_fetch_failed deployment_id=%s", row.id)
                self._fail(row, stage="extracting", safe_message=_GENERIC_FAILURE_MESSAGE)
                return

            self._run_pipeline(
                user=None,
                site=site,
                row=row,
                upload_path=zip_path,
                source_type="zip",
                mode=mode,
                custom_domain=custom_domain,
            )
        finally:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
