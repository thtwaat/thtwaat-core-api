"""THTWAAT Deploy Phase 4B — environment-variable resolution, snapshotting,
and framework-specific public/private splitting.

This module is the ONLY place decrypted environment variable values exist
in this process outside app/static_sites/env_crypto.py itself. Everything
here is trusted backend/build-pipeline code — never call resolve_*() from a
user-facing API path and never let a ResolvedEnvVar's ``value`` reach an API
response, log line, or exception message.

Lifecycle (see StaticSiteService in service.py for the actual wiring):

    live static_site_env_vars (encrypted)
        -> snapshot_env_vars() copies CIPHERTEXT ONLY into
           static_site_deployment_env_vars, tied to one deployment_id
        -> resolve_deployment_env_vars() decrypts that immutable snapshot
        -> vite_client_vars()/nextjs_public_build_vars()/
           nextjs_server_runtime_vars() split by framework prefix rules
        -> passed into run_vite_build()/run_nextjs_build()/start_runtime()

A later edit to the site's live env vars never touches an existing
deployment's snapshot — that is the whole point of snapshotting before build
starts (Phase 4B spec §10/§17).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List
from uuid import UUID

from app.static_sites.env_crypto import EnvVarCryptoError, decrypt_value
from app.static_sites.models import StaticSiteDeploymentEnvVar, StaticSitePreviewDeploymentEnvVar

if TYPE_CHECKING:
    from app.static_sites.repository import StaticSiteRepository

# Keys with either prefix are safe to inline into a CLIENT bundle at build
# time — see check_secret_public_prefix() in schemas.py, which is what stops
# a secret from ever being tagged with one of these prefixes in the first
# place. Kept in sync with app/static_sites/schemas.py's constants.
VITE_PUBLIC_PREFIX = "VITE_"
NEXTJS_PUBLIC_PREFIX = "NEXT_PUBLIC_"

# Defense in depth against an unbounded env-var set turning into an
# unbounded docker argv / HTTP payload to the build orchestrator.
MAX_ENV_VARS_PER_DEPLOYMENT = 100


class EnvVarResolutionError(Exception):
    """Environment resolution failed — the caller MUST fail the deployment
    cleanly (Phase 4B spec §16), never start a build/runtime with a partial
    variable set, and never fall back to plaintext or another environment.
    Message is always safe to log/persist — never includes a value."""


@dataclass(frozen=True)
class ResolvedEnvVar:
    key: str
    value: str  # decrypted plaintext — trusted-code-only, see module docstring
    is_secret: bool
    environment: str


def snapshot_env_vars(
    repo: "StaticSiteRepository", *, deployment_id: UUID, workspace_id: UUID, site_id: UUID, environment: str
) -> List[StaticSiteDeploymentEnvVar]:
    """Copy the site's CURRENT live env vars for exactly one environment into
    an immutable snapshot tied to deployment_id. Copies ciphertext only —
    never decrypts — so a snapshot can always be taken even if the
    encryption key were (hypothetically) unavailable; decryption is deferred
    to resolve_deployment_env_vars() at actual build/runtime time. Must be
    called before any build/runtime container starts.

    Takes the SAME StaticSiteRepository instance the caller already uses for
    deployment CRUD (rather than constructing its own) — one repo per
    request/pipeline run, not a second hidden one."""
    live_rows = repo.list_env_vars(site_id, workspace_id, environment=environment)
    snapshot_rows = [
        StaticSiteDeploymentEnvVar(
            deployment_id=deployment_id,
            key=row.key,
            encrypted_value=row.encrypted_value,
            environment=row.environment,
            is_secret=row.is_secret,
        )
        for row in live_rows
    ]
    return repo.create_deployment_env_var_snapshot(snapshot_rows)


def clone_env_var_snapshot(
    repo: "StaticSiteRepository", *, from_deployment_id: UUID, to_deployment_id: UUID
) -> List[StaticSiteDeploymentEnvVar]:
    """Rollback support: copy a PRIOR deployment's already-immutable snapshot
    onto the new rollback deployment row, rather than re-resolving the site's
    (possibly since-changed) live env vars (Phase 4B spec §11 — rollback must
    restore the artifact AND the environment exactly as that version used
    them, never the current live config)."""
    source_rows = repo.list_deployment_env_var_snapshot(from_deployment_id)
    cloned_rows = [
        StaticSiteDeploymentEnvVar(
            deployment_id=to_deployment_id,
            key=row.key,
            encrypted_value=row.encrypted_value,
            environment=row.environment,
            is_secret=row.is_secret,
        )
        for row in source_rows
    ]
    return repo.create_deployment_env_var_snapshot(cloned_rows)


def resolve_deployment_env_vars(repo: "StaticSiteRepository", *, deployment_id: UUID) -> List[ResolvedEnvVar]:
    """Decrypt one deployment's immutable snapshot. Fails closed: if ANY row
    fails to decrypt, the whole resolution fails (Phase 4B spec §16) — never
    returns a partial set."""
    rows = repo.list_deployment_env_var_snapshot(deployment_id)
    if len(rows) > MAX_ENV_VARS_PER_DEPLOYMENT:
        raise EnvVarResolutionError(
            f"This deployment has more than {MAX_ENV_VARS_PER_DEPLOYMENT} environment variables."
        )
    resolved: List[ResolvedEnvVar] = []
    for row in rows:
        try:
            value = decrypt_value(row.encrypted_value)
        except EnvVarCryptoError as exc:
            raise EnvVarResolutionError(
                f"Failed to resolve environment variable '{row.key}' for this deployment."
            ) from exc
        resolved.append(
            ResolvedEnvVar(key=row.key, value=value, is_secret=bool(row.is_secret), environment=row.environment)
        )
    return resolved


def snapshot_preview_env_vars(
    repo: "StaticSiteRepository", *, preview_deployment_id: UUID, workspace_id: UUID, site_id: UUID
) -> List[StaticSitePreviewDeploymentEnvVar]:
    """THTWAAT Deploy Phase 6A — preview counterpart of snapshot_env_vars().
    Hardcoded to environment="preview" (never "production"/"development"):
    a preview build must only ever see vars a company operator explicitly
    tagged for previews — see StaticSitePreviewDeploymentEnvVar's docstring
    for why there is deliberately no fallback to production vars here."""
    live_rows = repo.list_env_vars(site_id, workspace_id, environment="preview")
    snapshot_rows = [
        StaticSitePreviewDeploymentEnvVar(
            preview_deployment_id=preview_deployment_id,
            key=row.key,
            encrypted_value=row.encrypted_value,
            environment=row.environment,
            is_secret=row.is_secret,
        )
        for row in live_rows
    ]
    return repo.create_preview_env_var_snapshot(snapshot_rows)


def resolve_preview_env_vars(repo: "StaticSiteRepository", *, preview_deployment_id: UUID) -> List[ResolvedEnvVar]:
    """Decrypt one preview's immutable snapshot. Same fail-closed contract as
    resolve_deployment_env_vars() — never returns a partial set."""
    rows = repo.list_preview_env_var_snapshot(preview_deployment_id)
    if len(rows) > MAX_ENV_VARS_PER_DEPLOYMENT:
        raise EnvVarResolutionError(
            f"This preview has more than {MAX_ENV_VARS_PER_DEPLOYMENT} environment variables."
        )
    resolved: List[ResolvedEnvVar] = []
    for row in rows:
        try:
            value = decrypt_value(row.encrypted_value)
        except EnvVarCryptoError as exc:
            raise EnvVarResolutionError(
                f"Failed to resolve environment variable '{row.key}' for this preview."
            ) from exc
        resolved.append(
            ResolvedEnvVar(key=row.key, value=value, is_secret=bool(row.is_secret), environment=row.environment)
        )
    return resolved


def vite_client_vars(resolved: List[ResolvedEnvVar]) -> Dict[str, str]:
    """Only VITE_* — these become browser-visible via import.meta.env at
    build time. Vite output is static (no server runtime), so there is no
    separate "server-only" injection point for a Vite deployment; anything
    without this prefix is simply never passed to the build."""
    return {r.key: r.value for r in resolved if r.key.startswith(VITE_PUBLIC_PREFIX)}


def nextjs_public_build_vars(resolved: List[ResolvedEnvVar]) -> Dict[str, str]:
    """Only NEXT_PUBLIC_* — inlined into the client bundle at build time via
    Next.js's process.env.NEXT_PUBLIC_* replacement."""
    return {r.key: r.value for r in resolved if r.key.startswith(NEXTJS_PUBLIC_PREFIX)}


def nextjs_server_runtime_vars(resolved: List[ResolvedEnvVar]) -> Dict[str, str]:
    """ALL resolved vars (both NEXT_PUBLIC_* and server-only) — matches real
    Next.js semantics: server-side code can read every var via process.env,
    NEXT_PUBLIC_* included; only the CLIENT bundle is restricted to the
    public subset (see nextjs_public_build_vars)."""
    return {r.key: r.value for r in resolved}


def secret_values(resolved: List[ResolvedEnvVar]) -> List[str]:
    """Plaintext values of every is_secret=true var — feeds the redaction set
    in app/static_sites/env_redaction.py. Never logged, never persisted."""
    return [r.value for r in resolved if r.is_secret and r.value]
