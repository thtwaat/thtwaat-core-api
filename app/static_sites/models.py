"""THTWAAT Deploy ORM — static_sites + static_site_deployments.

Deliberately a sibling to app/studio's StudioProject/StudioProjectDeployment,
not a reuse of those tables: StudioProject.prompt is NOT NULL (AI-pipeline
specific) and StudioProjectDeployment.project_id is a NOT NULL CASCADE FK to
studio_projects — reusing either would mean either inventing a fake prompt
or weakening a live FK constraint the existing Studio deploy flow relies on.
This module mirrors the exact same versioning/rollback/audit conventions
(id/workspace_id/version/is_current/status/stage/urls/health/ssl/
instructions/logs/rollback_of/created_by) instead of forking them.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin


class StaticSite(Base, TimestampMixin):
    """A static-website project a company deploys HTML/ZIP uploads to."""

    __tablename__ = "static_sites"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_static_sites_workspace_slug"),
        Index("ix_static_sites_workspace", "workspace_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(64), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)


class StaticSiteDeployment(Base, TimestampMixin):
    """One immutable static-site deployment version (upload → extract → live)."""

    __tablename__ = "static_site_deployments"
    __table_args__ = (
        UniqueConstraint("site_id", "version", name="uq_static_site_deploys_site_version"),
        Index("ix_static_site_deploys_site_current", "site_id", "is_current"),
        Index("ix_static_site_deploys_site_status", "site_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    site_id = Column(
        UUID(as_uuid=True),
        ForeignKey("static_sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    provider = Column(String(64), nullable=False, default="static")
    status = Column(String(32), nullable=False, default="queued")
    stage = Column(String(64), nullable=False, default="queued")

    # Source metadata — never a build_id/approval_id, this bypasses the AI
    # Software Factory entirely (source_type: "html" | "zip").
    source_type = Column(String(16), nullable=False, default="zip")
    upload_filename = Column(String(255), nullable=True)
    upload_size_bytes = Column(Integer, nullable=False, default=0)

    # THTWAAT Deploy Phase 5C — where source_type="zip"'s bytes actually came
    # from: "upload" (manual HTML/ZIP upload, the only value before this
    # phase) or "github" (fetched server-side from a connected repository's
    # exact pinned commit — see app/static_sites/github_client.py's archive
    # fetch and StaticSiteService.run_github_deploy). Deliberately a separate
    # column from source_type rather than overloading it: source_type still
    # only ever describes the EXTRACTION mechanics prepare_deployment() must
    # run (html vs zip), while source_provider is provenance for the UI/audit
    # trail. github_* fields are NULL for every "upload" row.
    source_provider = Column(String(16), nullable=False, default="upload")
    github_repository_owner = Column(String(255), nullable=True)
    github_repository_name = Column(String(255), nullable=True)
    # Exact pinned commit SHA this deployment was built from (never a moving
    # ref like "main" or "latest") — spec §8. Full 40-char hex, validated in
    # app/static_sites/github_webhook.py before this row is ever created.
    github_commit_sha = Column(String(64), nullable=True)
    github_branch = Column(String(255), nullable=True)
    # Detected project framework (app/static_sites/vite_detect.py):
    # "static_html" | "static_zip" | "vite" | "nextjs". NULL until detection
    # runs (mid-pipeline) or copied from the target deployment on rollback.
    framework = Column(String(32), nullable=True)
    # Isolated, server-generated, immutable extraction root for this version —
    # <STATIC_SITES_DIR>/<workspace_id>/<site_id>/<deployment_id>/ — never
    # derived from the uploaded filename or hostname. For framework="nextjs"
    # this holds the immutable standalone runtime artifact (server.js,
    # .next/static, public/, pruned node_modules) instead of static HTML.
    deployment_path = Column(Text, nullable=True)

    # THTWAAT Deploy Phase 3 (Next.js) — how this version is served.
    # "static" (nginx root/try_files, the only mode before this phase) or
    # "node" (nginx proxies to an isolated per-deployment runtime container —
    # see app/static_sites/nextjs_runtime.py). NULL/"static" for every row
    # created before this phase.
    runtime_type = Column(String(16), nullable=True, default="static")
    # Fixed, server-generated container name (thtwaat-nextjs-runtime-<hex>) —
    # never a raw Docker container id — so nginx can address it by Docker
    # embedded DNS and so rollback/cutover can validate+stop it later. NULL
    # for static deployments and for nextjs deployments that haven't started
    # a runtime yet.
    runtime_container_id = Column(String(128), nullable=True)
    # Fixed internal container port (settings.NEXTJS_RUNTIME_PORT, currently
    # always 3000) — recorded per row for observability/debugging even though
    # no host port is ever allocated or published (see nginx_gen.py).
    internal_port = Column(Integer, nullable=True)
    # "pending" | "healthy" | "unhealthy" | "stopped" — last known result of
    # the post-start health probe (app/static_sites/nextjs_runtime.py). NULL
    # for static deployments.
    health_status = Column(String(16), nullable=True)

    domain = Column(String(255), nullable=True)
    subdomain = Column(String(255), nullable=True)
    environment = Column(String(32), nullable=False, default="production")
    live = Column(Boolean, nullable=False, default=False)
    urls = Column(JSONB, nullable=False, default=dict)
    health = Column(JSONB, nullable=False, default=dict)
    ssl = Column(JSONB, nullable=False, default=dict)
    instructions = Column(JSONB, nullable=False, default=list)
    logs = Column(JSONB, nullable=False, default=list)

    file_count = Column(Integer, nullable=False, default=0)
    total_bytes = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    retryable = Column(Boolean, nullable=False, default=False)
    rollback_of = Column(UUID(as_uuid=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)


class StaticSiteUploadIdempotency(Base, TimestampMixin):
    """Client-supplied Idempotency-Key -> deployment mapping for
    POST /upload (Phase 2 staging validation report §6/§12: the upload
    endpoint runs the whole build pipeline synchronously, so a retried or
    duplicated request must resolve to the SAME deployment, not launch a
    second Docker build). One row per (site_id, idempotency_key) — the
    unique constraint is the actual concurrency guard (see
    StaticSiteRepository.claim_idempotency_key): two requests racing on the
    same key can both attempt the insert, but only one commits.

    A separate table rather than a column on static_site_deployments because
    the key must be claimed BEFORE the deployment row's own pipeline starts
    (the row is the thing being deduplicated, not a property of it), and so
    that expiring old keys (see purge_expired) is a plain bulk DELETE that
    never touches deployment history.
    """

    __tablename__ = "static_site_upload_idempotency"
    __table_args__ = (
        UniqueConstraint("site_id", "idempotency_key", name="uq_static_site_idempotency_site_key"),
        Index("ix_static_site_idempotency_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    site_id = Column(
        UUID(as_uuid=True),
        ForeignKey("static_sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idempotency_key = Column(String(200), nullable=False)
    deployment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("static_site_deployments.id", ondelete="CASCADE"),
        nullable=False,
    )


class StaticSiteEnvironmentVariable(Base, TimestampMixin):
    """THTWAAT Deploy Phase 4A — a single KEY -> encrypted-value pair scoped
    to one site + one deployment environment.

    ``encrypted_value`` (never ``value``) is the only place the value is
    persisted — see app/static_sites/env_crypto.py. ``environment`` is a
    plain String rather than a DB enum so a later phase can add "preview"
    without an ALTER TYPE migration; validation of the allowed set lives in
    app/static_sites/schemas.py instead. Phase 4A stores/serves metadata and
    encrypted values only — build/runtime injection is Phase 4B.
    """

    __tablename__ = "static_site_env_vars"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "environment", "key", name="uq_static_site_env_vars_site_env_key"
        ),
        Index("ix_static_site_env_vars_workspace", "workspace_id"),
        Index("ix_static_site_env_vars_site", "site_id"),
        Index("ix_static_site_env_vars_site_environment", "site_id", "environment"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_id = Column(
        UUID(as_uuid=True),
        ForeignKey("static_sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(255), nullable=False)
    encrypted_value = Column(Text, nullable=False)
    environment = Column(String(32), nullable=False, default="production")
    is_secret = Column(Boolean, nullable=False, default=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class StaticSiteDeploymentEnvVar(Base, TimestampMixin):
    """THTWAAT Deploy Phase 4B — immutable per-deployment environment
    variable snapshot.

    Copied verbatim (ciphertext only — never decrypted) from
    StaticSiteEnvironmentVariable at the moment a deployment starts (see
    app/static_sites/env_resolver.py::snapshot_env_vars). A later edit to the
    site's live static_site_env_vars rows must never change what an
    already-running deployment (or a future rollback to it) actually used —
    that guarantee is this table's entire reason to exist. Rows are never
    updated after insert, only read (build/runtime injection) or deleted via
    CASCADE when the owning deployment is deleted.
    """

    __tablename__ = "static_site_deployment_env_vars"
    __table_args__ = (
        UniqueConstraint(
            "deployment_id", "key", name="uq_static_site_deployment_env_vars_deployment_key"
        ),
        Index("ix_static_site_deployment_env_vars_deployment", "deployment_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    deployment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("static_site_deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(255), nullable=False)
    encrypted_value = Column(Text, nullable=False)
    environment = Column(String(32), nullable=False)
    is_secret = Column(Boolean, nullable=False, default=True)


class StaticSitePreviewDeployment(Base, TimestampMixin):
    """THTWAAT Deploy Phase 6A — one ephemeral preview environment per
    (site, GitHub PR number).

    Deliberately a SIBLING table to StaticSiteDeployment, not a mode on it:
    StaticSiteDeployment is built around exactly one current version per
    site (is_current, UniqueConstraint(site_id, version),
    find_previous_completed() as the rollback-candidate source) — mixing
    preview rows into it would put ephemeral PR content into the rollback
    candidate pool. UniqueConstraint(site_id, pr_number) means synchronize/
    reopen UPDATE this same row in place (generation += 1) rather than
    versioning like production; a preview only ever needs to show its
    CURRENT generation, never full build history.

    Structural preview/production isolation (not just a filter that could
    be forgotten): separate table, separate env-var snapshot table (see
    StaticSitePreviewDeploymentEnvVar), separate filesystem namespace
    (.../previews/<preview_id>/<generation>/ — see
    app/static_sites/provider.py::preview_deployment_directory), separate
    hostname namespace (pr-<n>-... — see preview_hostname.py). Previews
    ALWAYS use the platform-owned free-subdomain zone, never a customer's
    own custom domain, even if the site's production deployment is on one.
    """

    __tablename__ = "static_site_preview_deployments"
    __table_args__ = (
        UniqueConstraint("site_id", "pr_number", name="uq_static_site_previews_site_pr"),
        Index("ix_static_site_previews_site", "site_id"),
        Index("ix_static_site_previews_expires_at", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    site_id = Column(
        UUID(as_uuid=True), ForeignKey("static_sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    pr_number = Column(Integer, nullable=False)
    branch = Column(String(255), nullable=False)  # PR head ref (source branch)
    base_branch = Column(String(255), nullable=True)  # PR base ref — must equal connection.selected_branch
    # Trusted repository identity copied from GitHubConnection at creation
    # time — never the webhook payload's free-text repository.owner.login/
    # name (see app/static_sites/github_webhook_router.py).
    github_repository_owner = Column(String(255), nullable=True)
    github_repository_name = Column(String(255), nullable=True)
    # Exact pinned commit SHA of the CURRENT generation — never a moving ref.
    commit_sha = Column(String(64), nullable=False)
    # Stale-build guard key (see StaticSiteService._mark_if_superseded's
    # generation-scoped sibling in preview_service.py): incremented on every
    # opened/synchronize/reopened; a worker job pins the generation it was
    # enqueued for and re-checks this column before AND after building.
    generation = Column(Integer, nullable=False, default=1)

    status = Column(String(16), nullable=False, default="queued")  # queued|building|ready|failed|torn_down
    stage = Column(String(64), nullable=False, default="queued")  # reuses provider.STAGES vocabulary

    hostname = Column(String(255), nullable=True)
    deployment_path = Column(Text, nullable=True)
    framework = Column(String(32), nullable=True)
    runtime_type = Column(String(16), nullable=True, default="static")
    runtime_container_id = Column(String(128), nullable=True)
    internal_port = Column(Integer, nullable=True)
    health_status = Column(String(16), nullable=True)

    urls = Column(JSONB, nullable=False, default=dict)
    logs = Column(JSONB, nullable=False, default=list)
    error = Column(Text, nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)
    torn_down_at = Column(DateTime(timezone=True), nullable=True)
    # pr_closed | expired | manual | build_failed_cleanup
    teardown_reason = Column(String(32), nullable=True)

    source_provider = Column(String(16), nullable=False, default="github")


class StaticSitePreviewDeploymentEnvVar(Base, TimestampMixin):
    """Immutable per-generation environment variable snapshot for ONE
    preview deployment — sibling of StaticSiteDeploymentEnvVar, same shape,
    same crypto (app/static_sites/env_crypto.py), same redaction. A
    deliberate separate table (not a second nullable FK on the production
    table) so production's already-battle-tested snapshot/clone/rollback
    code path is never touched by this phase.

    Preview builds resolve ONLY environment="preview"-tagged live vars —
    never a fallback to "production" vars (see env_resolver.py's
    snapshot_preview_env_vars/resolve_preview_env_vars): a PR — potentially
    from a less-trusted contributor — must never receive production secrets.
    """

    __tablename__ = "static_site_preview_deployment_env_vars"
    __table_args__ = (
        UniqueConstraint(
            "preview_deployment_id", "key", name="uq_static_site_preview_env_vars_preview_key"
        ),
        Index("ix_static_site_preview_env_vars_preview", "preview_deployment_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    preview_deployment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("static_site_preview_deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(255), nullable=False)
    encrypted_value = Column(Text, nullable=False)
    environment = Column(String(32), nullable=False)
    is_secret = Column(Boolean, nullable=False, default=True)


class GitHubConnection(Base, TimestampMixin):
    """THTWAAT Deploy Phase 5 — one GitHub repository/branch connection per
    static site (connection layer only; no auto-deploy/webhooks yet).

    Deliberately holds NO GitHub access/refresh token. This is a GitHub App
    installation, not an OAuth App: ``installation_id`` is a non-secret
    identifier, and every GitHub API call mints a short-lived installation
    access token on demand (see app/static_sites/github_client.py) that is
    never persisted. ``github_username``/``github_account_id`` are read once
    at connect time via GET /app/installations/{id} (app-JWT auth) — no user
    OAuth code exchange ever happens, so there is no user token to store or
    leak in the first place.
    """

    __tablename__ = "github_connections"
    __table_args__ = (
        UniqueConstraint("site_id", name="uq_github_connections_site"),
        Index("ix_github_connections_workspace", "workspace_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_id = Column(
        UUID(as_uuid=True),
        ForeignKey("static_sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installation_id = Column(String(64), nullable=False)
    github_account_id = Column(String(64), nullable=False)
    github_username = Column(String(255), nullable=False)
    account_type = Column(String(32), nullable=True)

    # Null until POST .../github/select is called.
    repository_owner = Column(String(255), nullable=True)
    repository_name = Column(String(255), nullable=True)
    repository_id = Column(String(64), nullable=True)
    default_branch = Column(String(255), nullable=True)
    selected_branch = Column(String(255), nullable=True)

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class GitHubOAuthState(Base, TimestampMixin):
    """THTWAAT Deploy Phase 5 — single-use CSRF state for the GitHub App
    installation flow.

    ``state_hash`` (sha256 hex of the raw state value handed to the client)
    mirrors app/auth/model.py's PasswordResetToken.token_hash convention —
    the raw value only ever exists in the redirect URL, never at rest.
    Binding user_id/workspace_id/site_id at issuance (rather than trusting
    anything the callback request itself claims) is what lets
    /github/callback safely resolve "who is this for" from an unauthenticated
    GitHub redirect. consumed_at is set atomically by
    StaticSiteRepository.consume_state on first use — that single UPDATE...
    WHERE consumed_at IS NULL is the actual replay guard, not application
    logic layered on top of a plain SELECT.
    """

    __tablename__ = "github_oauth_states"
    __table_args__ = (
        Index("ix_github_oauth_states_expires_at", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    state_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    site_id = Column(UUID(as_uuid=True), ForeignKey("static_sites.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)


class GitHubWebhookDelivery(Base, TimestampMixin):
    """THTWAAT Deploy Phase 5C — idempotency claim for one inbound GitHub
    webhook delivery (X-GitHub-Delivery header).

    GitHub retries webhook deliveries on timeout/5xx; the SAME delivery must
    never trigger a second deployment. One row per delivery id — like
    StaticSiteUploadIdempotency/BillingWebhookEvent, the UniqueConstraint on
    delivery_id (not any application-level check) is what actually makes the
    claim atomic under concurrent/retried deliveries (see
    StaticSiteRepository.claim_github_webhook_delivery: two requests racing
    on the same delivery id can both attempt the INSERT, only one commits).

    Deliberately does NOT store the webhook payload or any GitHub credential
    — only enough to dedupe and audit which repository/event a delivery was
    for.
    """

    __tablename__ = "github_webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_github_webhook_deliveries_delivery_id"),
        Index("ix_github_webhook_deliveries_repository", "repository_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    delivery_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    repository_id = Column(String(64), nullable=True)
    # "received" (claimed, not yet resolved) -> "queued" (deployment
    # enqueued) | "ignored" (valid signature, not actionable — wrong
    # branch/repo not connected/non-push event/branch deleted) | "failed"
    # (an unexpected error while processing this delivery).
    status = Column(String(16), nullable=False, default="received")
    processed_at = Column(DateTime(timezone=True), nullable=True)
