"""PreviewDeploymentService — THTWAAT Deploy Phase 6A (Preview Deployments).

Sibling to StaticSiteService, not a fork of it: every low-level primitive
(prepare_deployment, run_vite_build/run_nextjs_build via prepare_deployment,
nextjs_runtime.start_runtime/stop_runtime, bind_hostname_and_ssl,
publish_deploy_event, env_crypto/env_redaction, github_client) is reused
UNCHANGED. What's new here is orchestration for a fundamentally different
lifecycle shape: N simultaneously-live rows per site keyed by PR number,
updated in place across "generations" (opened/synchronize/reopened) rather
than versioned like production, with an expiry and an explicit teardown.

RBAC/company-scoping/audit conventions are copied verbatim from
StaticSiteService (see app/static_sites/service.py) — same
can_manage_company_users gate, same EnterpriseService.audit() call shape.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
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
    nextjs_server_runtime_vars,
    resolve_preview_env_vars,
    secret_values,
    snapshot_preview_env_vars,
)
from app.static_sites.github_webhook import PullRequestEvent
from app.static_sites.models import GitHubConnection, StaticSite, StaticSitePreviewDeployment
from app.static_sites.preview_hostname import allocate_preview_subdomain
from app.static_sites.provider import (
    StaticDeployContext,
    StaticDeployError,
    bind_hostname_and_ssl,
    prepare_deployment,
    preview_deployment_directory,
    static_site_root,
)
from app.static_sites.repository import StaticSiteRepository
from app.static_sites.schemas import PreviewDeploymentListResponse, PreviewDeploymentResponse

logger = logging.getLogger(__name__)

_GENERIC_FAILURE_MESSAGE = "Preview deployment failed due to an internal error. Our team has been notified."


class PreviewDeploymentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StaticSiteRepository(db)

    # ---- shared helpers (mirror StaticSiteService exactly) ------------------

    def _require_deploy_manager(self, user: UserProfileResponse) -> None:
        if not can_manage_company_users(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company owners and admins can manage preview deployments",
            )

    def _get_site(self, user: UserProfileResponse, site_id: UUID) -> StaticSite:
        site = self.repo.get_site_for_workspace(site_id, UUID(str(user.company_id)))
        if not site:
            raise HTTPException(status_code=404, detail="Static site not found")
        return site

    def _audit(self, *, company_id: UUID, action: str, resource_id: str, metadata: Optional[dict] = None) -> None:
        try:
            from app.enterprise.models import AuditSeverity
            from app.enterprise.service import EnterpriseService

            EnterpriseService(self.db).audit(
                company_id,
                None,  # webhook-driven — no authenticated human actor
                action=action,
                resource_type="static_site_preview_deployment",
                resource_id=resource_id,
                severity=AuditSeverity.INFO,
                metadata=metadata or {},
                commit=True,
            )
        except Exception:  # noqa: BLE001
            logger.warning("preview_deploy_audit_failed action=%s", action)

    def _emit(self, preview_id: UUID, stage: str, **data: Any) -> None:
        try:
            from app.studio.deploy_events import publish_deploy_event

            publish_deploy_event(preview_id, stage, {"stage": stage, **data})
        except Exception:  # noqa: BLE001
            logger.debug("preview_deploy_event_publish_failed stage=%s", stage)

    def _sync_usage(self, workspace_id: UUID) -> None:
        try:
            from app.usage.dimensions import UsageDimension
            from app.usage.service import UsageService

            count = self.repo.count_active_previews_for_company(workspace_id)
            UsageService(self.db).record(
                workspace_id, UsageDimension.PREVIEW_DEPLOYMENTS, count, source="preview_deployment"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("preview_usage_sync_failed workspace_id=%s err=%s", workspace_id, exc)

    def _to_response(self, row: StaticSitePreviewDeployment) -> PreviewDeploymentResponse:
        return PreviewDeploymentResponse.model_validate(row)

    # ---- webhook-facing entrypoint (fast path — see github_webhook_router.py) --

    def create_or_advance(
        self, *, site: StaticSite, connection: GitHubConnection, event: PullRequestEvent
    ) -> StaticSitePreviewDeployment:
        """opened/synchronize/reopened all funnel through here. A brand-new
        PR (or a reopen of a previously torn-down one) is a NEW active
        preview and must clear the billing quota gate BEFORE the row is
        created/resurrected; a synchronize of an already-active preview
        does not change the active count, so no quota check runs there —
        mirrors app/domains/service.py's create()'s
        "count = live count; check_quota(count + 1)" pattern exactly.

        Raises HTTPException(429) on quota breach (caller — the webhook
        router — decides how to surface that to GitHub, never lets it
        propagate as a raw failure to a webhook delivery).
        """
        existing = self.repo.get_preview_by_pr(site.id, event.pr_number)
        ttl = timedelta(hours=int(getattr(settings, "PREVIEW_DEPLOYMENT_TTL_HOURS", 72) or 72))
        now = datetime.now(timezone.utc)

        is_new_active_preview = existing is None or existing.torn_down_at is not None
        if is_new_active_preview:
            from app.usage.dimensions import UsageDimension
            from app.usage.service import UsageService

            count = self.repo.count_active_previews_for_company(site.workspace_id)
            UsageService(self.db).check_quota(
                site.workspace_id, UsageDimension.PREVIEW_DEPLOYMENTS, quantity=count + 1
            )

        if existing is None:
            row = StaticSitePreviewDeployment(
                site_id=site.id,
                workspace_id=site.workspace_id,
                pr_number=event.pr_number,
                branch=event.head_ref,
                base_branch=event.base_ref,
                github_repository_owner=connection.repository_owner,
                github_repository_name=connection.repository_name,
                commit_sha=event.head_sha,
                generation=1,
                status="queued",
                stage="queued",
                hostname=allocate_preview_subdomain(
                    site_id=site.id, site_name=site.name, pr_number=event.pr_number
                ),
                urls={},
                logs=[
                    {"stage": "queued", "message": f"Pull request #{event.pr_number} opened"},
                    {"stage": "queued", "message": f"Commit {event.head_sha[:12]} pinned"},
                ],
                expires_at=now + ttl,
                source_provider="github",
            )
            row = self.repo.create_preview(row)
        else:
            row = existing
            reopened = row.torn_down_at is not None
            row.branch = event.head_ref
            row.base_branch = event.base_ref
            row.commit_sha = event.head_sha
            row.generation = int(row.generation or 1) + 1
            row.status = "queued"
            row.stage = "queued"
            row.expires_at = now + ttl
            if reopened:
                row.torn_down_at = None
                row.teardown_reason = None
                if not row.hostname:
                    row.hostname = allocate_preview_subdomain(
                        site_id=site.id, site_name=site.name, pr_number=event.pr_number
                    )
            row.logs = list(row.logs or []) + [
                {
                    "stage": "queued",
                    "message": (
                        f"Pull request #{event.pr_number} reopened, commit {event.head_sha[:12]} pinned"
                        if reopened
                        else f"Pull request #{event.pr_number} synchronized, commit {event.head_sha[:12]} pinned"
                    ),
                }
            ]
            row = self.repo.save_preview(row)

        self._emit(row.id, "queued", message="Preview deployment queued", pr_number=row.pr_number)
        if is_new_active_preview:
            self._sync_usage(site.workspace_id)
        self._audit(
            company_id=site.workspace_id,
            action="preview_deploy.queued",
            resource_id=str(row.id),
            metadata={
                "site_id": str(site.id), "pr_number": row.pr_number, "branch": row.branch,
                "commit_sha": row.commit_sha, "generation": row.generation,
            },
        )
        return row

    def request_close(self, *, site: StaticSite, pr_number: int, reason: str = "pr_closed") -> Optional[UUID]:
        """PR closed webhook — returns the preview_id to enqueue a teardown
        job for, or None if there is no active preview for this PR (nothing
        to tear down — a PR can close without ever having a preview, e.g.
        it targeted an untracked branch)."""
        row = self.repo.get_preview_by_pr(site.id, pr_number)
        if row is None or row.torn_down_at is not None:
            return None
        return row.id

    # ---- worker entrypoints ---------------------------------------------------

    def _synthetic_generation_id(self, preview_id: UUID, generation: int) -> UUID:
        """Deterministic-but-distinct UUID per (preview_id, generation) —
        previews reuse the SAME row/id across generations (unlike
        production, where a new deployment row = a new UUID), so a
        per-generation-unique id is needed anywhere a physical resource
        (staging dir, Next.js runtime container name) must never collide
        between an old generation still serving traffic and a new one
        building — see the zero-downtime cutover below."""
        return uuid.uuid5(preview_id, str(int(generation)))

    def run_preview_deploy(self, preview_id: UUID, generation: int) -> None:
        """Worker entrypoint for job type "static_site.preview_deploy". The
        job payload pins BOTH preview_id and the generation it was
        enqueued for — the stale-build guard (mirrors
        StaticSiteService._mark_if_superseded, generation-scoped instead of
        version-scoped) checks this TWICE: once here at job start (cheap,
        skips even fetching the archive for an already-superseded build)
        and once again right before hostname/runtime cutover (a
        synchronize can land — via the webhook HTTP handler, a different
        process — while this build is still running)."""
        row = self.repo.get_preview(preview_id)
        if row is None:
            logger.error("preview_deploy_row_missing preview_id=%s", preview_id)
            return
        if row.torn_down_at is not None:
            logger.info("preview_deploy_skipped_torn_down preview_id=%s", preview_id)
            return
        if int(row.generation or 0) != int(generation):
            logger.info(
                "preview_deploy_stale_at_start preview_id=%s job_generation=%s current_generation=%s",
                preview_id, generation, row.generation,
            )
            return

        site = self.repo.get_site(row.site_id)
        if site is None:
            self._fail(row, safe_message=_GENERIC_FAILURE_MESSAGE)
            return
        connection = self.repo.get_github_connection(site.id, site.workspace_id)
        if connection is None or not connection.repository_id or not connection.installation_id:
            self._fail(row, safe_message="GitHub is no longer connected for this site.")
            return

        # Captured BEFORE this generation's build touches anything — the
        # previous generation's artifact/runtime stays up and serving this
        # preview's hostname until the NEW generation passes its own health
        # check (Phase 3/11-style zero-downtime cutover, reused
        # conceptually for previews).
        previous_deployment_path = row.deployment_path
        previous_runtime_container_id = row.runtime_container_id

        gen_id = self._synthetic_generation_id(row.id, generation)
        dest_dir = preview_deployment_directory(site.workspace_id, site.id, row.id, generation)
        zip_path = static_site_root() / "_preview_incoming" / f"{gen_id}.zip"

        row.status = "building"
        row.stage = "validating"
        self.repo.save_preview(row)
        self._emit(row.id, "building", message="Preview build started")

        try:
            try:
                snapshot_preview_env_vars(
                    self.repo, preview_deployment_id=row.id, workspace_id=site.workspace_id, site_id=site.id
                )
                resolved_env_vars = resolve_preview_env_vars(self.repo, preview_deployment_id=row.id)
            except EnvVarResolutionError as exc:
                self._fail(row, safe_message=str(exc))
                return
            redact = build_secret_redactor(secret_values(resolved_env_vars))

            async def _fetch() -> None:
                token = await github_client.mint_installation_token(connection.installation_id)
                await github_client.fetch_repository_archive(
                    token, connection.repository_owner, connection.repository_name, row.commit_sha,
                    dest_path=zip_path,
                )

            try:
                asyncio.run(_fetch())
            except github_client.GitHubApiError as exc:
                self._fail(row, safe_message=str(exc.detail))
                return
            except Exception:  # noqa: BLE001
                logger.exception("preview_archive_fetch_failed preview_id=%s", row.id)
                self._fail(row, safe_message=_GENERIC_FAILURE_MESSAGE)
                return

            row.stage = "building"
            self.repo.save_preview(row)
            self._emit(row.id, "building", message="Building preview")

            def _on_stage(stage: str, message: str) -> None:
                row.stage = stage
                self.repo.save_preview(row)
                self._emit(row.id, stage, message=message)

            try:
                extract_info = prepare_deployment(
                    upload_path=zip_path, source_type="zip", dest_dir=dest_dir,
                    deployment_id=gen_id, workspace_id=site.workspace_id, site_id=site.id,
                    stage_callback=_on_stage, resolved_env_vars=resolved_env_vars,
                )
            except StaticDeployError as exc:
                row.logs = list(row.logs or []) + [
                    {"stage": "building", "message": line} for line in redact_lines(exc.log_lines or [], redact)
                ]
                self._fail(row, safe_message=str(exc), dest_dir=dest_dir)
                return

            # Guard #2 — re-read from the DB (not the in-memory row this
            # method has held since job start): a concurrent
            # opened/synchronize/reopened webhook, handled by the API
            # server process, may have advanced this preview's generation
            # while this build was running. If so, this build's output is
            # discarded — never activated, never left mutating the row.
            current = self.repo.get_preview(preview_id)
            if current is None or current.torn_down_at is not None or int(current.generation or 0) != int(generation):
                logger.info(
                    "preview_deploy_stale_before_activation preview_id=%s job_generation=%s current_generation=%s",
                    preview_id, generation, current.generation if current else None,
                )
                shutil.rmtree(dest_dir, ignore_errors=True)
                return

            row.framework = str(extract_info.get("framework") or "static_zip")
            row.logs = list(row.logs or []) + [
                {"stage": "building", "message": line}
                for line in redact_lines(extract_info.get("build_log") or [], redact)
            ]
            self.repo.save_preview(row)

            runtime_target: Optional[str] = None
            if row.framework == "nextjs":
                live = (
                    self.repo.count_live_nextjs_runtimes(site.workspace_id)
                    + self.repo.count_live_preview_nextjs_runtimes(site.workspace_id)
                )
                if live >= settings.NEXTJS_MAX_RUNTIMES_PER_COMPANY:
                    self._fail(
                        row,
                        safe_message=(
                            f"This company has reached its limit of {settings.NEXTJS_MAX_RUNTIMES_PER_COMPANY} "
                            "live Next.js deployments (production + previews combined). Close or wait for a "
                            "preview to expire before opening another."
                        ),
                        dest_dir=dest_dir,
                    )
                    return

                row.stage = "runtime_starting"
                self.repo.save_preview(row)
                self._emit(row.id, "runtime_starting", message="Starting isolated preview runtime")
                try:
                    runtime_result = nextjs_runtime.start_runtime(
                        artifact_dir=dest_dir, deployment_id=gen_id,
                        server_env_vars=nextjs_server_runtime_vars(resolved_env_vars),
                    )
                except nextjs_runtime.RuntimeError_ as exc:
                    row.logs = list(row.logs or []) + [
                        {"stage": "runtime_starting", "message": line}
                        for line in redact_lines(exc.log_lines or [], redact)
                    ]
                    self._fail(row, safe_message=str(exc), dest_dir=dest_dir)
                    return

                row.runtime_type = "node"
                row.runtime_container_id = runtime_result.container_name
                row.internal_port = int(settings.NEXTJS_RUNTIME_PORT)
                row.health_status = "healthy" if runtime_result.healthy else "unhealthy"
                self.repo.save_preview(row)
                runtime_target = nextjs_runtime.proxy_target(runtime_result.container_name)
            else:
                row.runtime_type = "static"

            hostname = row.hostname
            ctx = StaticDeployContext(
                site_id=site.id, deployment_id=row.id, workspace_id=site.workspace_id,
                site_name=site.name, version=row.generation, db_session=self.db, actor_user_id=None,
            )

            row.stage = "domain"
            self.repo.save_preview(row)
            self._emit(row.id, "domain", message=f"Assigning hostname {hostname}")

            ssl_status = ""
            if previous_deployment_path is None and previous_runtime_container_id is None:
                # First generation ever to reach this point for this PR —
                # full free-subdomain bind (creates the CompanyDomain row +
                # SSL cert), reusing the EXACT same call production's
                # free-subdomain path uses. Same real DNS check
                # resolve_deploy_hostname()'s free_subdomain branch does —
                # never assume the platform wildcard record is resolvable.
                from app.studio.domain_validation import validate_hostname

                try:
                    dns_validated = not validate_hostname(hostname, suggested_free=hostname).nxdomain
                    ssl_info = bind_hostname_and_ssl(
                        ctx, self._progress_noop, hostname=hostname, mode="free_subdomain",
                        dns_validated=dns_validated,
                        deployment_dir=None if runtime_target else dest_dir, runtime_target=runtime_target,
                    )
                    ssl_status = str(ssl_info.get("ssl_status") or "").upper()
                except Exception:  # noqa: BLE001
                    logger.exception("preview_domain_bind_failed preview_id=%s hostname=%s", row.id, hostname)
            else:
                # Subsequent generation of the SAME PR: the hostname/domain
                # row already exists and is (or was) already live — just
                # repoint it at this generation's new artifact/runtime,
                # exactly like StaticSiteService.rollback()'s SSL repoint.
                try:
                    from app.domains.service import DomainService
                    from app.ssl.manager import SslManager

                    domain_row = DomainService(self.db).repo.get_by_hostname(hostname)
                    if domain_row is not None:
                        ssl_manager = SslManager(self.db)
                        if runtime_target:
                            result = ssl_manager.set_runtime_proxy_target(
                                domain_row.id, site.workspace_id, runtime_target, site.workspace_id
                            )
                        else:
                            result = ssl_manager.set_static_root(
                                domain_row.id, site.workspace_id, str(dest_dir), site.workspace_id
                            )
                        ssl_status = str(result.get("ssl_status") or "").upper()
                except Exception:  # noqa: BLE001
                    logger.exception("preview_domain_repoint_failed preview_id=%s hostname=%s", row.id, hostname)

            row.stage = "health_check"
            self.repo.save_preview(row)
            live = False
            if ssl_status in {"ACTIVE", "ISSUED"} or previous_deployment_path or previous_runtime_container_id:
                from app.studio.deploy import probe_http

                health = probe_http(f"https://{hostname}/")
                live = bool(health.get("ok"))

            row.deployment_path = str(dest_dir)
            row.status = "ready"
            row.stage = "completed"
            row.health_status = row.health_status or ("healthy" if live else "unhealthy")
            row.urls = {"website": f"https://{hostname}"} if hostname else {}
            row.logs = list(row.logs or []) + [
                {"stage": "completed", "message": "Preview live" if live else "Preview deployed"}
            ]
            self.repo.save_preview(row)
            self._emit(row.id, "ready", message="Preview ready", live=live, url=row.urls.get("website"))

            # Cutover complete — only now stop/remove the PREVIOUS
            # generation's runtime and directory (they stayed up and
            # untouched for this entire build).
            if previous_runtime_container_id and previous_runtime_container_id != row.runtime_container_id:
                self._stop_runtime_safely(previous_runtime_container_id)
            if previous_deployment_path and previous_deployment_path != str(dest_dir):
                shutil.rmtree(Path(previous_deployment_path), ignore_errors=True)

            self._audit(
                company_id=site.workspace_id, action="preview_deploy.ready", resource_id=str(row.id),
                metadata={
                    "site_id": str(site.id), "pr_number": row.pr_number, "hostname": hostname,
                    "commit_sha": row.commit_sha, "generation": row.generation,
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("preview_deploy_pipeline_failed preview_id=%s", row.id)
            self._fail(row, safe_message=_GENERIC_FAILURE_MESSAGE, dest_dir=dest_dir)
        finally:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass

    def _progress_noop(self, stage: str, payload: Dict[str, Any]) -> None:
        logger.debug("preview_deploy_domain_progress stage=%s payload=%s", stage, payload)

    def _stop_runtime_safely(self, container_name: Optional[str]) -> None:
        if not container_name:
            return
        try:
            nextjs_runtime.stop_runtime(container_name)
        except Exception:  # noqa: BLE001
            logger.warning("preview_runtime_stop_failed container=%s", container_name)

    def _fail(
        self, row: StaticSitePreviewDeployment, *, safe_message: str, dest_dir: Optional[Path] = None
    ) -> None:
        self._stop_runtime_safely(row.runtime_container_id)
        row.status = "failed"
        row.stage = "failed"
        row.error = safe_message
        row.health_status = "stopped" if row.runtime_container_id else row.health_status
        row.logs = list(row.logs or []) + [{"stage": "failed", "message": safe_message}]
        self.repo.save_preview(row)
        self._emit(row.id, "failed", message=safe_message)
        if dest_dir is not None:
            shutil.rmtree(dest_dir, ignore_errors=True)

    def teardown(self, preview_id: UUID, *, reason: str = "pr_closed") -> None:
        """Worker entrypoint for job type "static_site.preview_teardown".
        Idempotent — a preview already torn down is a silent no-op, safe to
        retry (PR-closed, expiry sweep, and manual-close can all race to
        enqueue this for the same preview)."""
        row = self.repo.get_preview(preview_id)
        if row is None or row.torn_down_at is not None:
            return

        self._stop_runtime_safely(row.runtime_container_id)

        hostname = row.hostname
        if hostname:
            try:
                from app.domains.service import DomainService
                from app.ssl.nginx_gen import reload_nginx, remove_vhost

                domain_row = DomainService(self.db).repo.get_by_hostname(hostname)
                # Explicit vhost removal + reload — DomainService.delete()
                # itself does not touch nginx (confirmed: it only deletes
                # the row and invalidates the CORS cache), so teardown must
                # do this itself or the dead preview's vhost config lingers.
                remove_vhost(hostname)
                reload_nginx()
                if domain_row is not None:
                    DomainService(self.db).delete(domain_row.id, row.workspace_id, row.workspace_id)
            except Exception:  # noqa: BLE001
                logger.exception("preview_teardown_domain_cleanup_failed preview_id=%s hostname=%s", row.id, hostname)

        if row.deployment_path:
            try:
                # row.deployment_path is ".../previews/<preview_id>/<generation>/"
                # — remove the WHOLE preview's tree (every generation, this
                # preview only), i.e. its immediate parent. Deliberately
                # NOT .parent.parent, which would be the shared "previews/"
                # directory for the entire site (every OTHER preview too).
                preview_root = Path(row.deployment_path).parent
                if preview_root.name == str(row.id):
                    shutil.rmtree(preview_root, ignore_errors=True)
            except Exception:  # noqa: BLE001
                logger.warning("preview_teardown_cleanup_failed preview_id=%s", row.id)

        row.status = "torn_down"
        row.stage = "torn_down"
        row.torn_down_at = datetime.now(timezone.utc)
        row.teardown_reason = reason
        row.runtime_container_id = None
        row.health_status = "stopped"
        row.deployment_path = None
        row.logs = list(row.logs or []) + [{"stage": "torn_down", "message": f"Preview torn down ({reason})"}]
        self.repo.save_preview(row)
        self._emit(row.id, "torn_down", message="Preview torn down", reason=reason)
        self._sync_usage(row.workspace_id)
        self._audit(
            company_id=row.workspace_id, action="preview_deploy.torn_down", resource_id=str(row.id),
            metadata={"site_id": str(row.site_id), "pr_number": row.pr_number, "reason": reason},
        )

    # ---- authenticated read/manage API (see preview_router.py) ----------------

    def list_previews(
        self, user: UserProfileResponse, site_id: UUID, *, page: int = 1, per_page: int = 30
    ) -> PreviewDeploymentListResponse:
        self._require_deploy_manager(user)
        site = self._get_site(user, site_id)
        page = max(1, int(page))
        per_page = max(1, min(100, int(per_page)))
        rows, total = self.repo.list_previews_for_site(
            site.id, site.workspace_id, limit=per_page, offset=(page - 1) * per_page
        )
        return PreviewDeploymentListResponse(
            items=[self._to_response(r) for r in rows], page=page, per_page=per_page, total=total
        )

    def get_preview(self, user: UserProfileResponse, site_id: UUID, preview_id: UUID) -> PreviewDeploymentResponse:
        self._require_deploy_manager(user)
        site = self._get_site(user, site_id)
        row = self.repo.get_preview_for_workspace(preview_id, site.id, site.workspace_id)
        if not row:
            raise HTTPException(status_code=404, detail="Preview deployment not found")
        return self._to_response(row)

    def request_manual_teardown(self, user: UserProfileResponse, site_id: UUID, preview_id: UUID) -> PreviewDeploymentResponse:
        """Owners/admins can force-close a preview early. Async, per Phase
        6A's stated default: enqueues the SAME teardown job PR-close/expiry
        use rather than tearing down synchronously inside the request."""
        self._require_deploy_manager(user)
        site = self._get_site(user, site_id)
        row = self.repo.get_preview_for_workspace(preview_id, site.id, site.workspace_id)
        if not row:
            raise HTTPException(status_code=404, detail="Preview deployment not found")
        if row.torn_down_at is not None:
            return self._to_response(row)

        try:
            from app.monitoring.queue import enqueue

            enqueue({"type": "static_site.preview_teardown", "preview_id": str(row.id), "reason": "manual", "attempt": 1})
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Teardown queue is temporarily unavailable."
            ) from exc

        self._audit(
            company_id=site.workspace_id, action="preview_deploy.teardown_requested", resource_id=str(row.id),
            metadata={"site_id": str(site.id), "pr_number": row.pr_number},
        )
        return self._to_response(row)
