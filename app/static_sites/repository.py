"""Data access for THTWAAT Deploy — mirrors app/studio/repository.py's
deployment-table method shapes (create/save/get/list/current/clear/next_version)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.static_sites.models import (
    GitHubConnection,
    GitHubOAuthState,
    GitHubWebhookDelivery,
    StaticSite,
    StaticSiteDeployment,
    StaticSiteDeploymentEnvVar,
    StaticSiteEnvironmentVariable,
    StaticSitePreviewDeployment,
    StaticSitePreviewDeploymentEnvVar,
    StaticSiteUploadIdempotency,
)


class StaticSiteRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- sites ----------------------------------------------------------

    def create_site(self, site: StaticSite) -> StaticSite:
        self.db.add(site)
        self.db.commit()
        self.db.refresh(site)
        return site

    def get_site(self, site_id: UUID) -> Optional[StaticSite]:
        return self.db.query(StaticSite).filter(StaticSite.id == site_id).first()

    def get_site_for_workspace(self, site_id: UUID, workspace_id: UUID) -> Optional[StaticSite]:
        return (
            self.db.query(StaticSite)
            .filter(StaticSite.id == site_id, StaticSite.workspace_id == workspace_id)
            .first()
        )

    def get_site_by_slug(self, workspace_id: UUID, slug: str) -> Optional[StaticSite]:
        return (
            self.db.query(StaticSite)
            .filter(StaticSite.workspace_id == workspace_id, StaticSite.slug == slug)
            .first()
        )

    def list_sites(self, workspace_id: UUID, limit: int = 50, offset: int = 0) -> List[StaticSite]:
        return (
            self.db.query(StaticSite)
            .filter(StaticSite.workspace_id == workspace_id)
            .order_by(StaticSite.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    # ---- deployments ------------------------------------------------------

    def next_deployment_version(self, site_id: UUID) -> int:
        current = (
            self.db.query(StaticSiteDeployment.version)
            .filter(StaticSiteDeployment.site_id == site_id)
            .order_by(StaticSiteDeployment.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_deployments(self, site_id: UUID) -> None:
        (
            self.db.query(StaticSiteDeployment)
            .filter(
                StaticSiteDeployment.site_id == site_id,
                StaticSiteDeployment.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_deployment(self, row: StaticSiteDeployment) -> StaticSiteDeployment:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_deployment(self, deployment_id: UUID) -> None:
        """Only ever called on a row whose pipeline never started (the
        idempotency-race loser in deploy_upload() — see service.py) — never
        on a deployment that reached extraction/build/publish."""
        row = self.get_deployment(deployment_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()

    def save_deployment(self, row: StaticSiteDeployment) -> StaticSiteDeployment:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_deployment(self, deployment_id: UUID) -> Optional[StaticSiteDeployment]:
        return (
            self.db.query(StaticSiteDeployment)
            .filter(StaticSiteDeployment.id == deployment_id)
            .first()
        )

    def get_current_deployment(self, site_id: UUID, workspace_id: UUID) -> Optional[StaticSiteDeployment]:
        return (
            self.db.query(StaticSiteDeployment)
            .filter(
                StaticSiteDeployment.site_id == site_id,
                StaticSiteDeployment.workspace_id == workspace_id,
                StaticSiteDeployment.is_current.is_(True),
            )
            .order_by(StaticSiteDeployment.version.desc())
            .first()
        )

    def list_deployments(
        self, site_id: UUID, workspace_id: UUID, limit: int = 50
    ) -> List[StaticSiteDeployment]:
        return (
            self.db.query(StaticSiteDeployment)
            .filter(
                StaticSiteDeployment.site_id == site_id,
                StaticSiteDeployment.workspace_id == workspace_id,
            )
            .order_by(StaticSiteDeployment.version.desc())
            .limit(limit)
            .all()
        )

    def find_previous_completed(
        self, site_id: UUID, workspace_id: UUID, exclude_id: Optional[UUID] = None
    ) -> Optional[StaticSiteDeployment]:
        q = self.db.query(StaticSiteDeployment).filter(
            StaticSiteDeployment.site_id == site_id,
            StaticSiteDeployment.workspace_id == workspace_id,
            StaticSiteDeployment.status == "completed",
        )
        if exclude_id is not None:
            q = q.filter(StaticSiteDeployment.id != exclude_id)
        return q.order_by(StaticSiteDeployment.version.desc()).first()

    def count_live_nextjs_runtimes(self, workspace_id: UUID) -> int:
        """Number of this company's deployment rows that currently own a
        running Next.js runtime container — used to enforce
        settings.NEXTJS_MAX_RUNTIMES_PER_COMPANY (THTWAAT Phase 3 Phase 15:
        one tenant must not be able to exhaust VPS resources with unbounded
        long-lived processes). Deliberately counts rows with a
        runtime_container_id set and status="completed", not just
        is_current=True — a rollback target or an about-to-be-stopped
        previous version can briefly hold a live container too."""
        return (
            self.db.query(StaticSiteDeployment)
            .filter(
                StaticSiteDeployment.workspace_id == workspace_id,
                StaticSiteDeployment.runtime_type == "node",
                StaticSiteDeployment.runtime_container_id.isnot(None),
                StaticSiteDeployment.status == "completed",
            )
            .count()
        )

    # ---- upload idempotency ------------------------------------------------

    def get_idempotent_deployment(
        self, site_id: UUID, idempotency_key: str, *, ttl_hours: int = 24
    ) -> Optional[StaticSiteDeployment]:
        """The deployment a previous request with this same key already
        created, if that request is still within the TTL window — a request
        older than ttl_hours is treated as if the key had never been used
        (a fresh upload proceeds normally; see claim_idempotency_key)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        record = (
            self.db.query(StaticSiteUploadIdempotency)
            .filter(
                StaticSiteUploadIdempotency.site_id == site_id,
                StaticSiteUploadIdempotency.idempotency_key == idempotency_key,
                StaticSiteUploadIdempotency.created_at >= cutoff,
            )
            .first()
        )
        if record is None:
            return None
        return self.get_deployment(record.deployment_id)

    def claim_idempotency_key(self, site_id: UUID, idempotency_key: str, deployment_id: UUID) -> bool:
        """Atomically claim (site_id, idempotency_key) for deployment_id.

        Returns True if this call won the race (the caller should proceed
        with the pipeline for deployment_id); False if another request
        already claimed this exact key (the caller must discard the
        deployment row it just created — see delete_deployment — and use
        get_idempotent_deployment() to fetch the winner's deployment
        instead). The UniqueConstraint on (site_id, idempotency_key) is what
        actually makes this safe under real concurrency, not this method's
        own logic — two requests can both reach this call for the same key;
        only one INSERT can ever commit.
        """
        record = StaticSiteUploadIdempotency(
            site_id=site_id, idempotency_key=idempotency_key, deployment_id=deployment_id
        )
        self.db.add(record)
        try:
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            return False

    def purge_expired_idempotency_keys(self, *, ttl_hours: int = 24) -> int:
        """Bulk-delete idempotency records older than the TTL — safe to run
        at any time (get_idempotent_deployment() already ignores expired
        rows on its own; this is housekeeping, not a correctness
        requirement). Returns the number of rows removed. See
        scripts/scheduler.py for the periodic caller."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        deleted = (
            self.db.query(StaticSiteUploadIdempotency)
            .filter(StaticSiteUploadIdempotency.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return int(deleted)

    # ---- environment variables (THTWAAT Deploy Phase 4A) -------------------

    def create_env_var(self, row: StaticSiteEnvironmentVariable) -> StaticSiteEnvironmentVariable:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_env_var(self, env_id: UUID) -> Optional[StaticSiteEnvironmentVariable]:
        return (
            self.db.query(StaticSiteEnvironmentVariable)
            .filter(StaticSiteEnvironmentVariable.id == env_id)
            .first()
        )

    def get_env_var_by_key(
        self, site_id: UUID, environment: str, key: str
    ) -> Optional[StaticSiteEnvironmentVariable]:
        return (
            self.db.query(StaticSiteEnvironmentVariable)
            .filter(
                StaticSiteEnvironmentVariable.site_id == site_id,
                StaticSiteEnvironmentVariable.environment == environment,
                StaticSiteEnvironmentVariable.key == key,
            )
            .first()
        )

    def list_env_vars(
        self, site_id: UUID, workspace_id: UUID, environment: Optional[str] = None
    ) -> List[StaticSiteEnvironmentVariable]:
        q = self.db.query(StaticSiteEnvironmentVariable).filter(
            StaticSiteEnvironmentVariable.site_id == site_id,
            StaticSiteEnvironmentVariable.workspace_id == workspace_id,
        )
        if environment:
            q = q.filter(StaticSiteEnvironmentVariable.environment == environment)
        return q.order_by(StaticSiteEnvironmentVariable.key.asc()).all()

    def save_env_var(self, row: StaticSiteEnvironmentVariable) -> StaticSiteEnvironmentVariable:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_env_var(self, row: StaticSiteEnvironmentVariable) -> None:
        self.db.delete(row)
        self.db.commit()

    # ---- deployment env var snapshots (THTWAAT Deploy Phase 4B) -------------

    def create_deployment_env_var_snapshot(
        self, rows: List[StaticSiteDeploymentEnvVar]
    ) -> List[StaticSiteDeploymentEnvVar]:
        """Bulk-insert an immutable snapshot for one deployment. Deliberately
        one commit for the whole set — a deployment must never end up with a
        partial snapshot (some keys captured, others not)."""
        if not rows:
            return []
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def list_deployment_env_var_snapshot(
        self, deployment_id: UUID
    ) -> List[StaticSiteDeploymentEnvVar]:
        return (
            self.db.query(StaticSiteDeploymentEnvVar)
            .filter(StaticSiteDeploymentEnvVar.deployment_id == deployment_id)
            .order_by(StaticSiteDeploymentEnvVar.key.asc())
            .all()
        )

    # ---- github connections (THTWAAT Deploy Phase 5) -----------------------

    def get_github_connection(self, site_id: UUID, workspace_id: UUID) -> Optional[GitHubConnection]:
        return (
            self.db.query(GitHubConnection)
            .filter(
                GitHubConnection.site_id == site_id,
                GitHubConnection.workspace_id == workspace_id,
            )
            .first()
        )

    def upsert_github_connection(self, row: GitHubConnection) -> GitHubConnection:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_github_connection(self, row: GitHubConnection) -> None:
        self.db.delete(row)
        self.db.commit()

    # ---- github oauth state (single-use CSRF token) ------------------------

    def create_github_oauth_state(self, row: GitHubOAuthState) -> GitHubOAuthState:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def consume_github_oauth_state(self, state_hash: str) -> Optional[GitHubOAuthState]:
        """Atomically claim a state row: matches only an unconsumed,
        unexpired row by hash, and marks it consumed in the same UPDATE.
        Returns None on any mismatch/expiry/already-consumed (the caller
        must not distinguish these cases in its response — see
        app/static_sites/github_service.py). This UPDATE...WHERE is the
        actual replay guard; a SELECT-then-UPDATE would race under
        concurrent callback requests carrying the same state."""
        now = datetime.now(timezone.utc)
        updated = (
            self.db.query(GitHubOAuthState)
            .filter(
                GitHubOAuthState.state_hash == state_hash,
                GitHubOAuthState.consumed_at.is_(None),
                GitHubOAuthState.expires_at > now,
            )
            .update({"consumed_at": now}, synchronize_session=False)
        )
        if not updated:
            self.db.commit()
            return None
        self.db.commit()
        return (
            self.db.query(GitHubOAuthState)
            .filter(GitHubOAuthState.state_hash == state_hash)
            .first()
        )

    def purge_expired_github_oauth_states(self, *, grace_hours: int = 24) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=grace_hours)
        deleted = (
            self.db.query(GitHubOAuthState)
            .filter(GitHubOAuthState.expires_at < cutoff)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return int(deleted)

    def list_github_connections_by_repository(
        self, *, repository_id: str, installation_id: str
    ) -> List[GitHubConnection]:
        """Resolve EVERY connected site for an inbound webhook — matched on
        GitHub's own stable repository_id AND the installation_id the
        webhook payload carries (spec §7: never trust repository NAME
        alone, and cross-check installation/account context so a webhook
        for repository A can never resolve to a connection belonging to a
        different company's site B).

        Deliberately returns a LIST, not a single row via .first(): there is
        no database uniqueness constraint on (repository_id, installation_id)
        — GitHub_connections only enforces one connection per site
        (uq_github_connections_site) — and more than one row can legitimately
        match here. Two confirmed real scenarios (traced through
        github_service.py's connect/select_repository/disconnect lifecycle
        before this was written, per the P0 cross-tenant investigation):
          1. The SAME company connects the SAME repo to two different sites
             (e.g. a staging site and a production site both built from one
             repo) — ordinary, intended multi-site-per-repo usage.
          2. Two DIFFERENT companies each hold their own GitHubConnection
             against the SAME underlying GitHub App installation_id — this
             happens whenever the installing GitHub account/org grants access
             to more than one THTWAAT company (e.g. an agency's installation
             used on behalf of more than one client company, or two THTWAAT
             companies run by collaborators on the same GitHub org) — GitHub
             hands back the SAME installation_id to every /github/callback
             for that account, and select_repository() never checks whether
             a repository_id is already selected elsewhere before saving.
        A single .first() with no ORDER BY previously picked an arbitrary one
        of these rows — silently dropping the other matching site's
        deployment/preview on some pushes, and (scenario 2) capable of
        routing a webhook to the wrong company's site entirely. The caller
        must now fan out over every row this returns (see
        github_webhook_router.py's _handle_push/_handle_pull_request), not
        assume there is only one. Order is stable (created_at, id) purely so
        behavior is deterministic and testable — it carries no authorization
        meaning; every returned row still gets its own independent branch
        check downstream.

        Never raises — an empty list is the "not connected" case, handled by
        the caller exactly like the previous None return."""
        return (
            self.db.query(GitHubConnection)
            .filter(
                GitHubConnection.repository_id == repository_id,
                GitHubConnection.installation_id == installation_id,
            )
            .order_by(GitHubConnection.created_at.asc(), GitHubConnection.id.asc())
            .all()
        )

    # ---- github webhook delivery idempotency (THTWAAT Deploy Phase 5C) -----

    def claim_github_webhook_delivery(
        self, *, delivery_id: str, event_type: str, repository_id: Optional[str]
    ) -> Optional[GitHubWebhookDelivery]:
        """Atomically claim one X-GitHub-Delivery id. Returns the new row if
        this call is the first to see this delivery (the caller should
        process it); returns None if a delivery with this id was already
        claimed (GitHub retried — the caller must treat this as a no-op
        success, never start a second deployment). Exactly the
        claim_webhook_event()/StaticSiteUploadIdempotency pattern: the
        UniqueConstraint on delivery_id is the actual race guard, not this
        method's own logic."""
        existing = (
            self.db.query(GitHubWebhookDelivery)
            .filter(GitHubWebhookDelivery.delivery_id == delivery_id)
            .first()
        )
        if existing is not None:
            return None

        row = GitHubWebhookDelivery(
            delivery_id=delivery_id, event_type=event_type, repository_id=repository_id, status="received"
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
            return row
        except IntegrityError:
            self.db.rollback()
            return None

    def mark_github_webhook_delivery(self, row: GitHubWebhookDelivery, *, status: str) -> None:
        row.status = status
        row.processed_at = datetime.now(timezone.utc)
        self.db.add(row)
        self.db.commit()

    # ---- preview deployments (THTWAAT Deploy Phase 6A) ----------------------

    def get_preview_by_pr(self, site_id: UUID, pr_number: int) -> Optional[StaticSitePreviewDeployment]:
        return (
            self.db.query(StaticSitePreviewDeployment)
            .filter(
                StaticSitePreviewDeployment.site_id == site_id,
                StaticSitePreviewDeployment.pr_number == pr_number,
            )
            .first()
        )

    def get_preview(self, preview_id: UUID) -> Optional[StaticSitePreviewDeployment]:
        return (
            self.db.query(StaticSitePreviewDeployment)
            .filter(StaticSitePreviewDeployment.id == preview_id)
            .first()
        )

    def get_preview_for_workspace(
        self, preview_id: UUID, site_id: UUID, workspace_id: UUID
    ) -> Optional[StaticSitePreviewDeployment]:
        return (
            self.db.query(StaticSitePreviewDeployment)
            .filter(
                StaticSitePreviewDeployment.id == preview_id,
                StaticSitePreviewDeployment.site_id == site_id,
                StaticSitePreviewDeployment.workspace_id == workspace_id,
            )
            .first()
        )

    def list_previews_for_site(
        self, site_id: UUID, workspace_id: UUID, *, limit: int = 30, offset: int = 0
    ) -> tuple[List[StaticSitePreviewDeployment], int]:
        q = self.db.query(StaticSitePreviewDeployment).filter(
            StaticSitePreviewDeployment.site_id == site_id,
            StaticSitePreviewDeployment.workspace_id == workspace_id,
        )
        total = q.count()
        rows = (
            q.order_by(StaticSitePreviewDeployment.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return rows, total

    def create_preview(self, row: StaticSitePreviewDeployment) -> StaticSitePreviewDeployment:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_preview(self, row: StaticSitePreviewDeployment) -> StaticSitePreviewDeployment:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_expired_previews(self, *, now: Optional[datetime] = None) -> List[StaticSitePreviewDeployment]:
        """Every still-active (never torn down) preview whose expires_at has
        passed — the scheduler enqueues a teardown job per row (see
        scripts/scheduler.py), mirroring the domain.auto_progress sweep."""
        cutoff = now or datetime.now(timezone.utc)
        return (
            self.db.query(StaticSitePreviewDeployment)
            .filter(
                StaticSitePreviewDeployment.torn_down_at.is_(None),
                StaticSitePreviewDeployment.expires_at.isnot(None),
                StaticSitePreviewDeployment.expires_at < cutoff,
            )
            .all()
        )

    def count_active_previews_for_company(self, workspace_id: UUID) -> int:
        """Live (not torn down) preview count across every site the company
        owns — feeds the UsageDimension.PREVIEW_DEPLOYMENTS gauge check
        (company-wide, matching how DOMAINS/AGENTS_COUNT are metered)."""
        return (
            self.db.query(StaticSitePreviewDeployment)
            .filter(
                StaticSitePreviewDeployment.workspace_id == workspace_id,
                StaticSitePreviewDeployment.torn_down_at.is_(None),
            )
            .count()
        )

    def count_live_preview_nextjs_runtimes(self, workspace_id: UUID) -> int:
        """Sibling of count_live_nextjs_runtimes() — previews with a live
        Next.js runtime container, counted SEPARATELY so the caller can sum
        production + preview runtimes against the SAME
        NEXTJS_MAX_RUNTIMES_PER_COMPANY cap (a company must not be able to
        bypass that cap by using previews as a side door)."""
        return (
            self.db.query(StaticSitePreviewDeployment)
            .filter(
                StaticSitePreviewDeployment.workspace_id == workspace_id,
                StaticSitePreviewDeployment.runtime_type == "node",
                StaticSitePreviewDeployment.runtime_container_id.isnot(None),
                StaticSitePreviewDeployment.torn_down_at.is_(None),
            )
            .count()
        )

    # ---- preview env var snapshots (THTWAAT Deploy Phase 6A) ----------------

    def create_preview_env_var_snapshot(
        self, rows: List[StaticSitePreviewDeploymentEnvVar]
    ) -> List[StaticSitePreviewDeploymentEnvVar]:
        if not rows:
            return []
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def list_preview_env_var_snapshot(
        self, preview_deployment_id: UUID
    ) -> List[StaticSitePreviewDeploymentEnvVar]:
        return (
            self.db.query(StaticSitePreviewDeploymentEnvVar)
            .filter(StaticSitePreviewDeploymentEnvVar.preview_deployment_id == preview_deployment_id)
            .order_by(StaticSitePreviewDeploymentEnvVar.key.asc())
            .all()
        )

    def clear_preview_env_var_snapshot(self, preview_deployment_id: UUID) -> None:
        """Called before re-snapshotting on synchronize/reopen — a fresh
        generation gets a fresh snapshot of the site's CURRENT preview vars,
        never a stale union with an earlier generation's."""
        (
            self.db.query(StaticSitePreviewDeploymentEnvVar)
            .filter(StaticSitePreviewDeploymentEnvVar.preview_deployment_id == preview_deployment_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()
