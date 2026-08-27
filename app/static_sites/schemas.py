"""Pydantic schemas for THTWAAT Deploy (static_sites API)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StaticSiteCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class StaticSiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class StaticSiteListResponse(BaseModel):
    items: List[StaticSiteResponse]
    total: int


class StaticSiteDeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID
    version: int
    is_current: bool
    provider: str
    status: str
    stage: str
    source_type: str
    source_provider: str = "upload"
    github_repository_owner: Optional[str] = None
    github_repository_name: Optional[str] = None
    github_commit_sha: Optional[str] = None
    github_branch: Optional[str] = None
    framework: Optional[str] = None
    upload_filename: Optional[str] = None
    runtime_type: Optional[str] = None
    runtime_container_id: Optional[str] = None
    internal_port: Optional[int] = None
    health_status: Optional[str] = None
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    environment: str
    live: bool
    urls: Dict[str, Any] = Field(default_factory=dict)
    health: Dict[str, Any] = Field(default_factory=dict)
    ssl: Dict[str, Any] = Field(default_factory=dict)
    instructions: List[Any] = Field(default_factory=list)
    logs: List[Any] = Field(default_factory=list)
    file_count: int
    total_bytes: int
    duration_ms: int
    error: Optional[str] = None
    retryable: bool
    rollback_of: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("source_provider", mode="before")
    @classmethod
    def _default_source_provider(cls, v: Optional[str]) -> str:
        # NULL only for rows created before THTWAAT Deploy Phase 5C added
        # this column (a real DB row always has "upload" via the migration's
        # backfill) — treat that the same as "upload" rather than a 500.
        return v or "upload"


class StaticSiteDeploymentListResponse(BaseModel):
    items: List[StaticSiteDeploymentResponse]
    total: int


class StaticSiteRollbackRequest(BaseModel):
    deployment_id: Optional[UUID] = None


# ---- THTWAAT Deploy Phase 4A — environment variables -----------------------

# Deliberately a plain set (not a DB enum — see StaticSiteEnvironmentVariable
# in models.py). THTWAAT Deploy Phase 6A adds "preview": a preview build
# resolves ONLY vars tagged "preview" (see env_resolver.py's
# resolve_preview_env_vars) — never a fallback to "production" — since a PR
# may come from a less-trusted contributor.
ALLOWED_ENV_VAR_ENVIRONMENTS = {"production", "development", "preview"}

# Same shape POSIX/shell environment variable names require: an uppercase
# letter or underscore, then letters/digits/underscores only. This alone
# rejects every disallowed example in the Phase 4A spec (spaces, hyphens,
# "FOO;rm", "$(command)", embedded newlines, null bytes) — nothing beyond
# regex matching is needed since the value is never interpreted as shell.
_ENV_VAR_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_ENV_VAR_KEY_MAX_LEN = 255
# Generous but bounded — env values can be JSON blobs/PEM certs, but an
# unbounded value is a resource-exhaustion vector against the DB row.
_ENV_VAR_VALUE_MAX_LEN = 65536

# THTWAAT Deploy Phase 4B — a key with either prefix is inlined into the
# CLIENT bundle (Vite's import.meta.env / Next.js's process.env replacement
# at build time). A secret can never safely carry one of these prefixes —
# see app/static_sites/env_resolver.py for the injection side of this rule.
VITE_PUBLIC_PREFIX = "VITE_"
NEXTJS_PUBLIC_PREFIX = "NEXT_PUBLIC_"


def check_secret_public_prefix(key: str, is_secret: bool) -> None:
    """Shared by the create schema (below) and env_vars_service.update_env_var
    (which must re-check this when is_secret flips to True on an existing
    row, since the key isn't part of the update payload). Raises ValueError
    — callers translate to whatever error type fits their layer."""
    if not is_secret:
        return
    if key.startswith(VITE_PUBLIC_PREFIX):
        raise ValueError("Secret variables cannot use the VITE_ public prefix.")
    if key.startswith(NEXTJS_PUBLIC_PREFIX):
        raise ValueError("Secret variables cannot use the NEXT_PUBLIC_ public prefix.")


def _validate_env_var_key(value: str) -> str:
    key = (value or "").strip()
    if not key or len(key) > _ENV_VAR_KEY_MAX_LEN or not _ENV_VAR_KEY_PATTERN.match(key):
        raise ValueError(
            "Invalid environment variable name. Use uppercase letters, digits, and "
            "underscores only, starting with a letter or underscore (e.g. OPENAI_API_KEY)."
        )
    return key


def _validate_env_var_value(value: str) -> str:
    # The value is opaque data — never parsed/executed as shell syntax. Only
    # a hard length cap and a reject on embedded null bytes (Postgres text
    # columns/psycopg reject these outright) are enforced here.
    if value is None or len(value) == 0:
        raise ValueError("Environment variable value must not be empty.")
    if "\x00" in value:
        raise ValueError("Environment variable value must not contain null bytes.")
    if len(value) > _ENV_VAR_VALUE_MAX_LEN:
        raise ValueError(f"Environment variable value exceeds {_ENV_VAR_VALUE_MAX_LEN} characters.")
    return value


def _validate_env_var_environment(value: str) -> str:
    env = (value or "").strip().lower()
    if env not in ALLOWED_ENV_VAR_ENVIRONMENTS:
        raise ValueError(
            f"environment must be one of: {', '.join(sorted(ALLOWED_ENV_VAR_ENVIRONMENTS))}"
        )
    return env


class StaticSiteEnvVarCreateRequest(BaseModel):
    key: str
    value: str
    environment: str = "production"
    is_secret: bool = True

    @field_validator("key")
    @classmethod
    def _check_key(cls, v: str) -> str:
        return _validate_env_var_key(v)

    @field_validator("value")
    @classmethod
    def _check_value(cls, v: str) -> str:
        return _validate_env_var_value(v)

    @field_validator("environment")
    @classmethod
    def _check_environment(cls, v: str) -> str:
        return _validate_env_var_environment(v)

    # is_secret + VITE_/NEXT_PUBLIC_ prefix is deliberately NOT checked here
    # via a model_validator: a whole-model validator failure makes FastAPI's
    # default 422 handler echo the ENTIRE input dict back — including
    # `value` — in the response body. StaticSiteEnvVarService.create_env_var()
    # performs this check instead (see check_secret_public_prefix below),
    # raising a plain HTTPException with no echoed payload, exactly like
    # update_env_var() already has to (its payload doesn't even carry `key`).


class StaticSiteEnvVarUpdateRequest(BaseModel):
    """Value and/or secrecy flag only — key identity and environment are
    immutable after creation (delete/create instead of renaming/moving)."""

    value: Optional[str] = None
    is_secret: Optional[bool] = None

    @field_validator("value")
    @classmethod
    def _check_value(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_env_var_value(v)


class StaticSiteEnvVarResponse(BaseModel):
    """Metadata only — never includes `value` or `encrypted_value`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID
    key: str
    environment: str
    is_secret: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class StaticSiteEnvVarListResponse(BaseModel):
    items: List[StaticSiteEnvVarResponse]
    total: int


# ---- THTWAAT Deploy Phase 5 — GitHub Connect --------------------------------
# Connection layer only (no auto-deploy/webhooks). GitHubConnectionResponse
# deliberately has no token/credential field to omit — see
# app/static_sites/models.py::GitHubConnection: a GitHub App installation
# never has a user access/refresh token to begin with.

_REPO_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class GitHubConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID
    connected: bool = True
    github_account_id: str
    github_username: str
    account_type: Optional[str] = None
    installation_id: str
    repository_owner: Optional[str] = None
    repository_name: Optional[str] = None
    repository_id: Optional[str] = None
    default_branch: Optional[str] = None
    selected_branch: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GitHubConnectStartResponse(BaseModel):
    authorize_url: str


class GitHubRepositoryResponse(BaseModel):
    repository_id: str
    owner: str
    name: str
    full_name: str
    private: bool
    default_branch: Optional[str] = None


class GitHubRepositoryListResponse(BaseModel):
    items: List[GitHubRepositoryResponse]
    page: int
    per_page: int


class GitHubBranchResponse(BaseModel):
    name: str
    protected: bool = False


class GitHubBranchListResponse(BaseModel):
    items: List[GitHubBranchResponse]
    page: int
    per_page: int


class GitHubSelectRepositoryRequest(BaseModel):
    repository_owner: str
    repository_name: str
    branch: str

    @field_validator("repository_owner", "repository_name")
    @classmethod
    def _check_repo_segment(cls, v: str) -> str:
        v = (v or "").strip()
        if not _REPO_NAME_PATTERN.match(v):
            raise ValueError("Invalid GitHub repository owner/name.")
        return v

    @field_validator("branch")
    @classmethod
    def _check_branch(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 255 or "\x00" in v:
            raise ValueError("Invalid branch name.")
        return v


# ---- THTWAAT Deploy Phase 6A — Preview Deployments --------------------------


class PreviewDeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID
    pr_number: int
    branch: str
    base_branch: Optional[str] = None
    github_repository_owner: Optional[str] = None
    github_repository_name: Optional[str] = None
    commit_sha: str
    generation: int
    status: str
    stage: str
    hostname: Optional[str] = None
    framework: Optional[str] = None
    runtime_type: Optional[str] = None
    health_status: Optional[str] = None
    urls: Dict[str, Any] = Field(default_factory=dict)
    logs: List[Any] = Field(default_factory=list)
    error: Optional[str] = None
    expires_at: Optional[datetime] = None
    torn_down_at: Optional[datetime] = None
    teardown_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PreviewDeploymentListResponse(BaseModel):
    items: List[PreviewDeploymentResponse]
    page: int
    per_page: int
    total: int
