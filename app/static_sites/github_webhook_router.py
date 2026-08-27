"""THTWAAT Deploy Phase 5C/6A — Git Push -> Auto Deploy + Preview
Deployments: inbound GitHub webhook.

A dedicated router (mirrors github_router.py's own rationale) so this
public, signature-authenticated surface has a self-contained diff and can
never accidentally disturb the authenticated GitHub Connect endpoints or the
manual HTML/ZIP upload path.

NO get_current_user dependency — GitHub itself POSTs here with no bearer
token available. Authentication is exclusively the X-Hub-Signature-256 HMAC
verified against the raw request body (app/static_sites/github_webhook.py),
computed with a webhook secret that lives only in server configuration
(settings.GITHUB_APP_WEBHOOK_SECRET) and is never accepted from the
request. Nothing in the payload (repository owner/name, branch, commit sha)
is trusted for anything beyond a lookup key until AFTER signature
verification succeeds, and even then the actual repository owner/name used
downstream (archive fetch, deployment metadata) comes from the STORED,
previously-verified GitHubConnection row — never re-trusted from the
payload's free-text repository.owner.login/repository.name (see
create_github_deployment()/create_or_advance() in service.py/
preview_service.py).

Deliberately returns fast (spec §11/§18): the only work done inline is
signature verification, event/branch/repository matching, and a single
cheap row insert/update — the actual clone/build/publish pipeline runs
async via the existing Redis job queue (scripts/worker.py's
"static_site.github_deploy"/"static_site.preview_deploy"/
"static_site.preview_teardown" job types), exactly mirroring how
StudioService.deploy() enqueues "studio.deploy".

Phase 6A adds `pull_request` handling (opened/synchronize/reopened/closed)
to this SAME endpoint — GitHub sends both event types to one configured
webhook URL, so no new route is needed, only a second branch below.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.database import get_db
from app.static_sites.github_webhook import (
    MalformedWebhookPayload,
    SUPPORTED_PR_ACTIONS,
    parse_pull_request_event,
    parse_push_event,
    verify_signature,
)
from app.static_sites.preview_service import PreviewDeploymentService
from app.static_sites.repository import StaticSiteRepository
from app.static_sites.service import StaticSiteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/studio/static-sites", tags=["THTWAAT Deploy — GitHub Webhook"])

_SUPPORTED_EVENTS = {"push", "pull_request"}


def _extract_best_effort_repository_id(raw_payload: dict) -> Optional[str]:
    try:
        repo = raw_payload.get("repository")
        if isinstance(repo, dict) and repo.get("id") is not None:
            return str(repo["id"])
    except Exception:  # noqa: BLE001
        pass
    return None


@router.post(
    "/github/webhook",
    summary="GitHub push/pull_request webhook (public — signature-authenticated, not JWT)",
    include_in_schema=False,
)
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: Optional[str] = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(default=None, alias="X-GitHub-Delivery"),
    db: Session = Depends(get_db),
):
    # 1) Signature FIRST — nothing below this line trusts a single byte of
    # the request until this passes. Reject missing header, malformed
    # header, and mismatch identically (401) — never an oracle for which.
    raw_body = await request.body()
    secret = (settings.GITHUB_APP_WEBHOOK_SECRET or "").strip()
    if not secret:
        # Never fall back to "accept unsigned" — an unconfigured secret
        # means this endpoint is not live, not that it's open.
        return JSONResponse(status_code=503, content={"detail": "GitHub webhooks are not configured."})
    if not verify_signature(raw_body, x_hub_signature_256, secret):
        logger.warning("github_webhook_invalid_signature delivery=%s event=%s", x_github_delivery, x_github_event)
        return JSONResponse(status_code=401, content={"detail": "Invalid webhook signature."})

    if not x_github_event:
        return JSONResponse(status_code=400, content={"detail": "Missing X-GitHub-Event header."})
    if not x_github_delivery:
        return JSONResponse(status_code=400, content={"detail": "Missing X-GitHub-Delivery header."})

    try:
        raw_payload = json.loads(raw_body)
        if not isinstance(raw_payload, dict):
            raise ValueError("payload is not a JSON object")
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Malformed webhook payload."})

    repo = StaticSiteRepository(db)

    if x_github_event == "ping":
        return JSONResponse(status_code=200, content={"pong": True})

    if x_github_event not in _SUPPORTED_EVENTS:
        claimed = repo.claim_github_webhook_delivery(
            delivery_id=x_github_delivery,
            event_type=x_github_event,
            repository_id=_extract_best_effort_repository_id(raw_payload),
        )
        if claimed is not None:
            repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "event": x_github_event})

    if x_github_event == "pull_request":
        return _handle_pull_request(raw_payload, x_github_delivery, repo=repo, db=db)
    return _handle_push(raw_payload, x_github_delivery, repo=repo, db=db)


def _handle_push(raw_payload: dict, delivery_id: str, *, repo: StaticSiteRepository, db: Session) -> JSONResponse:
    try:
        push = parse_push_event(raw_payload)
    except MalformedWebhookPayload as exc:
        return JSONResponse(status_code=400, content={"detail": f"Malformed push payload: {exc}"})

    claimed = repo.claim_github_webhook_delivery(
        delivery_id=delivery_id, event_type="push", repository_id=push.repository_id
    )
    if claimed is None:
        # GitHub retried a delivery we already processed (or are processing)
        # — never start a second deployment for it. Still a success ack.
        return JSONResponse(status_code=202, content={"accepted": True, "duplicate": True})

    if push.deleted:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "branch_deleted"})

    if not push.installation_id:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "missing_installation"})

    # Fan out over EVERY connection matching this exact (repository_id,
    # installation_id) — never assume there is at most one (see
    # list_github_connections_by_repository()'s docstring: the same repo can
    # be legitimately connected to more than one site, either within one
    # company or, via a shared GitHub App installation, across companies).
    # Each candidate still gets its own independent branch check below, so a
    # push never deploys a site that isn't tracking the pushed branch.
    connections = repo.list_github_connections_by_repository(
        repository_id=push.repository_id, installation_id=push.installation_id
    )
    matched = [
        c for c in connections
        if c.repository_id and c.selected_branch and push.branch is not None and push.branch == c.selected_branch
    ]
    if not connections:
        # No THTWAAT project has this exact (repository_id, installation_id)
        # connected and repo-selected — never trust repository name alone
        # (spec §7). A safe, generic ack; no information about whether the
        # repository exists elsewhere is disclosed.
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "not_connected"})
    if not matched:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "branch_mismatch"})

    service = StaticSiteService(db)
    deployment_ids: list[str] = []
    any_new = False

    for connection in matched:
        site = repo.get_site_for_workspace(connection.site_id, connection.workspace_id)
        if site is None:
            logger.error(
                "github_webhook_orphaned_connection connection_id=%s site_id=%s",
                connection.id, connection.site_id,
            )
            continue

        # Same-commit dedup (spec §12/§15): a distinct webhook delivery (its
        # own X-GitHub-Delivery id — e.g. a manual "Redeliver" from GitHub,
        # or two near-simultaneous deliveries that both resolve to the exact
        # same already-current commit+branch) must not launch a second build
        # of a commit this site is already deploying or has already
        # deployed. This is IN ADDITION to the delivery-id claim above,
        # which only catches GitHub's own retries of the SAME delivery.
        current = repo.get_current_deployment(site.id, site.workspace_id)
        if (
            current is not None
            and current.source_provider == "github"
            and current.github_commit_sha == push.commit_sha
            and current.github_branch == push.branch
        ):
            deployment_ids.append(str(current.id))
            continue

        deployment = service.create_github_deployment(
            site=site, connection=connection, commit_sha=push.commit_sha, branch=push.branch
        )

        try:
            from app.monitoring.queue import enqueue

            enqueue(
                {
                    "type": "static_site.github_deploy",
                    "deployment_id": str(deployment.id),
                    "site_id": str(site.id),
                    "workspace_id": str(site.workspace_id),
                    "attempt": 1,
                    "timeout_seconds": 900,
                }
            )
        except Exception:  # noqa: BLE001
            logger.exception("github_webhook_enqueue_failed deployment_id=%s", deployment.id)
            service.fail_deployment(deployment, safe_message="Deployment queue is temporarily unavailable.")
            repo.mark_github_webhook_delivery(claimed, status="failed")
            return JSONResponse(status_code=503, content={"detail": "Deployment queue is temporarily unavailable."})

        deployment_ids.append(str(deployment.id))
        any_new = True

    if not deployment_ids:
        # Every matched connection pointed at an orphaned site row — nothing
        # was deployed, but the delivery itself was handled without error.
        repo.mark_github_webhook_delivery(claimed, status="failed")
        return JSONResponse(status_code=500, content={"detail": "Internal error."})

    repo.mark_github_webhook_delivery(claimed, status="queued" if any_new else "ignored")
    if len(deployment_ids) > 1:
        # Fan-out happened (more than one connection matched this exact
        # repository_id+installation_id+branch — see
        # list_github_connections_by_repository()'s docstring for the two
        # legitimate scenarios). The full list is logged server-side only —
        # NEVER placed in the HTTP response body. In the shared-installation
        # scenario the matched connections can belong to DIFFERENT
        # companies' sites; bundling every deployment id into one webhook
        # ack response would hand each tenant's deployment identifier to
        # whoever can see that GitHub App's webhook delivery log, which is
        # not this endpoint's tenant boundary to relax. The response always
        # reports only the single deployment_id most relevant to the
        # delivery (the first one processed) — full detail belongs in logs,
        # never in the wire response.
        logger.info(
            "github_webhook_push_fanned_out_to_multiple_connections repository_id=%s installation_id=%s "
            "branch=%s deployment_ids=%s",
            push.repository_id, push.installation_id, push.branch, deployment_ids,
        )
    response: dict = {"accepted": True, "deployment_id": deployment_ids[0]}
    if not any_new:
        response["duplicate"] = True
    return JSONResponse(status_code=202, content=response)


def _handle_pull_request(
    raw_payload: dict, delivery_id: str, *, repo: StaticSiteRepository, db: Session
) -> JSONResponse:
    """THTWAAT Deploy Phase 6A — opened/synchronize/reopened/closed. Every
    other pull_request action (edited, labeled, review_requested, ...) is
    acknowledged and ignored below. Same repository-confusion/company-
    isolation/idempotency guarantees as _handle_push, reusing the exact same
    GitHubWebhookDelivery claim table and get_github_connection_by_repository
    lookup — pull_request deliveries dedupe through the identical mechanism.
    """
    try:
        pr_event = parse_pull_request_event(raw_payload)
    except MalformedWebhookPayload as exc:
        return JSONResponse(status_code=400, content={"detail": f"Malformed pull_request payload: {exc}"})

    claimed = repo.claim_github_webhook_delivery(
        delivery_id=delivery_id, event_type="pull_request", repository_id=pr_event.repository_id
    )
    if claimed is None:
        return JSONResponse(status_code=202, content={"accepted": True, "duplicate": True})

    if pr_event.action not in SUPPORTED_PR_ACTIONS:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "unsupported_action"})

    if not pr_event.installation_id:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "missing_installation"})

    # Fan out over EVERY connection matching this exact (repository_id,
    # installation_id) — same rationale as _handle_push above: the same repo
    # can legitimately be connected to more than one site.
    connections = repo.list_github_connections_by_repository(
        repository_id=pr_event.repository_id, installation_id=pr_event.installation_id
    )
    # Only PRs proposing to merge into a tracked production branch get a
    # preview — a PR against some other branch THTWAAT doesn't track never
    # triggers one (no new connection field needed for this).
    matched = [
        c for c in connections
        if c.repository_id and c.selected_branch and pr_event.base_ref == c.selected_branch
    ]
    if not connections:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "not_connected"})
    if not matched:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "base_branch_mismatch"})

    preview_service = PreviewDeploymentService(db)

    if pr_event.action == "closed":
        preview_ids: list[str] = []
        for connection in matched:
            site = repo.get_site_for_workspace(connection.site_id, connection.workspace_id)
            if site is None:
                logger.error(
                    "github_webhook_orphaned_connection connection_id=%s site_id=%s",
                    connection.id, connection.site_id,
                )
                continue
            preview_id = preview_service.request_close(site=site, pr_number=pr_event.pr_number, reason="pr_closed")
            if preview_id is None:
                continue
            try:
                from app.monitoring.queue import enqueue

                enqueue(
                    {"type": "static_site.preview_teardown", "preview_id": str(preview_id), "reason": "pr_closed", "attempt": 1}
                )
            except Exception:  # noqa: BLE001
                logger.exception("github_webhook_preview_teardown_enqueue_failed preview_id=%s", preview_id)
                repo.mark_github_webhook_delivery(claimed, status="failed")
                return JSONResponse(status_code=503, content={"detail": "Teardown queue is temporarily unavailable."})
            preview_ids.append(str(preview_id))

        if not preview_ids:
            repo.mark_github_webhook_delivery(claimed, status="ignored")
            return JSONResponse(status_code=200, content={"ignored": True, "reason": "no_active_preview"})
        repo.mark_github_webhook_delivery(claimed, status="queued")
        if len(preview_ids) > 1:
            # See the identical rationale in _handle_push above — never put
            # more than one tenant's preview id in the wire response.
            logger.info(
                "github_webhook_pr_closed_fanned_out_to_multiple_connections repository_id=%s "
                "installation_id=%s pr_number=%s preview_ids=%s",
                pr_event.repository_id, pr_event.installation_id, pr_event.pr_number, preview_ids,
            )
        response: dict = {"accepted": True, "preview_id": preview_ids[0], "action": "teardown"}
        return JSONResponse(status_code=202, content=response)

    # opened / synchronize / reopened
    if not getattr(settings, "PREVIEW_DEPLOYMENTS_ENABLED", True):
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "previews_disabled"})

    # Default: reject fork PRs — building arbitrary fork-submitted code and
    # exposing it on a public preview URL, even fully sandboxed, is a
    # materially larger trust boundary than a push/PR from someone with
    # write access to the repository itself.
    if pr_event.is_fork:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        return JSONResponse(status_code=200, content={"ignored": True, "reason": "fork_pr_rejected"})

    preview_ids = []
    quota_exceeded_count = 0
    for connection in matched:
        site = repo.get_site_for_workspace(connection.site_id, connection.workspace_id)
        if site is None:
            logger.error(
                "github_webhook_orphaned_connection connection_id=%s site_id=%s",
                connection.id, connection.site_id,
            )
            continue

        try:
            preview = preview_service.create_or_advance(site=site, connection=connection, event=pr_event)
        except HTTPException as exc:
            if exc.status_code == 429:
                # Quota breach — never surface a raw 429 to GitHub for an
                # ignorable condition; the company's own owner/admin sees
                # this in the previews list instead (no row is created at
                # all here). Other matched sites still proceed.
                quota_exceeded_count += 1
                continue
            raise

        try:
            from app.monitoring.queue import enqueue

            enqueue(
                {
                    "type": "static_site.preview_deploy",
                    "preview_id": str(preview.id),
                    "generation": preview.generation,
                    "site_id": str(site.id),
                    "workspace_id": str(site.workspace_id),
                    "attempt": 1,
                    "timeout_seconds": 900,
                }
            )
        except Exception:  # noqa: BLE001
            logger.exception("github_webhook_preview_enqueue_failed preview_id=%s", preview.id)
            repo.mark_github_webhook_delivery(claimed, status="failed")
            return JSONResponse(status_code=503, content={"detail": "Deployment queue is temporarily unavailable."})

        preview_ids.append(str(preview.id))

    if not preview_ids:
        repo.mark_github_webhook_delivery(claimed, status="ignored")
        reason = "quota_exceeded" if quota_exceeded_count else "no_active_preview"
        return JSONResponse(status_code=200, content={"ignored": True, "reason": reason})

    repo.mark_github_webhook_delivery(claimed, status="queued")
    if len(preview_ids) > 1:
        # See the identical rationale in _handle_push above — never put more
        # than one tenant's preview id in the wire response.
        logger.info(
            "github_webhook_pr_opened_fanned_out_to_multiple_connections repository_id=%s "
            "installation_id=%s pr_number=%s preview_ids=%s",
            pr_event.repository_id, pr_event.installation_id, pr_event.pr_number, preview_ids,
        )
    response = {"accepted": True, "preview_id": preview_ids[0]}
    return JSONResponse(status_code=202, content=response)
