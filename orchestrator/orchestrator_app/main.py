"""Build orchestrator — the only process with Docker socket (or socket-proxy)
access for the Vite build sandbox. See orchestrator/README.md.

Deliberately not a general-purpose Docker API. Every filesystem path, image
name, and container name is still computed server-side from validated UUIDs
(see app/build.py) — the caller never supplies a path, image name, mount, or
command. THTWAAT Deploy Phase 4B adds exactly one bounded extra field to
each request: ``env_vars``, a dict of KEY=VALUE pairs injected only as
additional ``docker run -e`` argv entries (never a shell command). This is a
deliberate, narrow widening of the attack surface described above, not an
oversight — every key is validated against the same shape a POSIX env var
name requires, capped at 100 entries, and each endpoint enforces its own
prefix rule (VITE_* / NEXT_PUBLIC_* / no restriction for the server-only
runtime) — both here AND again inside build.py/nextjs_build.py/
nextjs_runtime.py, which never trust that this layer's validation ran.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from orchestrator_app.build import BuildError, run_build
from orchestrator_app.nextjs_build import BuildError as NextjsBuildError
from orchestrator_app.nextjs_build import run_build as run_nextjs_build
from orchestrator_app.nextjs_runtime import RuntimeError_ as NextjsRuntimeError
from orchestrator_app.nextjs_runtime import is_running as nextjs_is_running
from orchestrator_app.nextjs_runtime import start_runtime as start_nextjs_runtime
from orchestrator_app.nextjs_runtime import stop_runtime as stop_nextjs_runtime
from orchestrator_app.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="THTWAAT Vite Build Orchestrator", docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # THTWAAT Deploy Phase 4B — FastAPI's default handler echoes the
    # rejected field VALUE back as "input" (and sometimes a raw exception
    # object under "ctx") in every error entry. Several request fields here
    # (env_vars) can legitimately carry a secret value that fails validation
    # (e.g. a server-only key sent to the Vite/Next.js build endpoints) —
    # never let that value round-trip into a 422 response. Keep only
    # loc/msg/type, which is enough for a caller to fix its request.
    sanitized = [
        {k: err[k] for k in ("type", "loc", "msg") if k in err}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": sanitized})


# THTWAAT Deploy Phase 4B — env var injection. Widens this service's
# narrow attack surface (see module docstring) by exactly one thing: a
# bounded dict of KEY=VALUE pairs, injected only as additional `docker run
# -e` argv entries (never a shell command, path, or image). Every key is
# still validated against the SAME shape a POSIX env var name requires
# (mirrors app/static_sites/schemas.py's ^[A-Z_][A-Z0-9_]*$) and each
# endpoint enforces its own prefix rule below — this process never trusts
# that the caller (api/worker) already filtered correctly.
_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_MAX_ENV_VARS = 100
_MAX_ENV_VALUE_LEN = 65536


def _validate_env_vars(env_vars: Dict[str, str]) -> Dict[str, str]:
    if len(env_vars) > _MAX_ENV_VARS:
        raise ValueError(f"Too many environment variables (max {_MAX_ENV_VARS}).")
    for key, value in env_vars.items():
        if not _ENV_KEY_RE.match(key):
            raise ValueError(f"Invalid environment variable name: {key!r}")
        if not isinstance(value, str) or "\x00" in value or len(value) > _MAX_ENV_VALUE_LEN:
            raise ValueError(f"Invalid value for environment variable {key!r}")
    return env_vars


def require_shared_secret(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {settings.ORCHESTRATOR_SHARED_SECRET}"
    # Constant-time-ish comparison isn't critical here (this sits behind
    # network isolation already — see docker-compose.prod.yml — this header
    # is defense in depth, not the primary boundary), but cheap to do right.
    import hmac

    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


class BuildRequest(BaseModel):
    model_config = {"extra": "forbid"}

    workspace_id: UUID
    site_id: UUID
    deployment_id: UUID
    install_cmd: Literal["ci", "install"]
    env_vars: Dict[str, str] = {}

    @field_validator("env_vars")
    @classmethod
    def _check_env_vars(cls, v: Dict[str, str]) -> Dict[str, str]:
        v = _validate_env_vars(v)
        # Vite build: client-visible vars only — VITE_* is the entire
        # allowed set (see app/static_sites/vite_build.py's identical rule).
        bad = [k for k in v if not k.startswith("VITE_")]
        if bad:
            raise ValueError(f"Only VITE_*-prefixed variables may be injected into a Vite build: {bad}")
        return v


class BuildResponse(BaseModel):
    success: bool
    file_count: int = 0
    total_bytes: int = 0
    duration_ms: int = 0
    error: str | None = None
    log_lines: list[str] = []


@app.get("/live")
def live():
    return {"status": "alive"}


@app.post("/v1/vite-builds", response_model=BuildResponse, dependencies=[Depends(require_shared_secret)])
def create_build(payload: BuildRequest) -> BuildResponse:
    try:
        result = run_build(
            workspace_id=payload.workspace_id,
            site_id=payload.site_id,
            deployment_id=payload.deployment_id,
            install_cmd=payload.install_cmd,
            env_vars=payload.env_vars,
        )
    except BuildError as exc:
        return BuildResponse(success=False, error=str(exc), log_lines=exc.log_lines)

    return BuildResponse(
        success=True,
        file_count=result.file_count,
        total_bytes=result.total_bytes,
        duration_ms=result.duration_ms,
        log_lines=result.log_lines,
    )


# ---- THTWAAT Phase 3 — Next.js builds + runtimes ---------------------------
#
# Same narrow-schema philosophy as /v1/vite-builds above: every field is a
# UUID or a fixed two/three-value enum, never a path/image/command. The
# runtime container_name path parameter on the two endpoints below is
# validated against CONTAINER_NAME_RE (thtwaat-nextjs-runtime-<hex> only)
# BEFORE it ever reaches a docker stop/rm/inspect call — see
# nextjs_runtime.py's _validate_name()/is_running() — so this process can
# never be made to touch any other container on the host by name.


class NextjsBuildRequest(BaseModel):
    model_config = {"extra": "forbid"}

    workspace_id: UUID
    site_id: UUID
    deployment_id: UUID
    install_cmd: Literal["ci", "install"]
    env_vars: Dict[str, str] = {}

    @field_validator("env_vars")
    @classmethod
    def _check_env_vars(cls, v: Dict[str, str]) -> Dict[str, str]:
        v = _validate_env_vars(v)
        # Next.js BUILD step: only NEXT_PUBLIC_* may be inlined into the
        # client bundle. Server-only vars go through NextjsRuntimeStartRequest
        # instead (see below) — never here.
        bad = [k for k in v if not k.startswith("NEXT_PUBLIC_")]
        if bad:
            raise ValueError(f"Only NEXT_PUBLIC_*-prefixed variables may be injected into a Next.js build: {bad}")
        return v


class NextjsBuildResponse(BaseModel):
    success: bool
    file_count: int = 0
    total_bytes: int = 0
    duration_ms: int = 0
    error: str | None = None
    log_lines: list[str] = []


_RESERVED_RUNTIME_KEYS = {"PORT", "HOSTNAME", "NODE_ENV"}


class NextjsRuntimeStartRequest(BaseModel):
    model_config = {"extra": "forbid"}

    workspace_id: UUID
    site_id: UUID
    artifact_id: UUID
    deployment_id: UUID
    env_vars: Dict[str, str] = {}

    @field_validator("env_vars")
    @classmethod
    def _check_env_vars(cls, v: Dict[str, str]) -> Dict[str, str]:
        v = _validate_env_vars(v)
        # Runtime: server-side only, so no prefix restriction — but the
        # fixed keys this module wires itself are never allowed to be
        # overridden by a caller-supplied value.
        return {k: val for k, val in v.items() if k not in _RESERVED_RUNTIME_KEYS}


class NextjsRuntimeStartResponse(BaseModel):
    success: bool
    container_name: str | None = None
    healthy: bool = False
    status_code: int | None = None
    error: str | None = None
    log_lines: list[str] = []


class NextjsRuntimeStatusResponse(BaseModel):
    running: bool


@app.post("/v1/nextjs-builds", response_model=NextjsBuildResponse, dependencies=[Depends(require_shared_secret)])
def create_nextjs_build(payload: NextjsBuildRequest) -> NextjsBuildResponse:
    try:
        result = run_nextjs_build(
            workspace_id=payload.workspace_id,
            site_id=payload.site_id,
            deployment_id=payload.deployment_id,
            install_cmd=payload.install_cmd,
            env_vars=payload.env_vars,
        )
    except NextjsBuildError as exc:
        return NextjsBuildResponse(success=False, error=str(exc), log_lines=exc.log_lines)

    return NextjsBuildResponse(
        success=True,
        file_count=result.file_count,
        total_bytes=result.total_bytes,
        duration_ms=result.duration_ms,
        log_lines=result.log_lines,
    )


@app.post(
    "/v1/nextjs-runtimes", response_model=NextjsRuntimeStartResponse, dependencies=[Depends(require_shared_secret)]
)
def create_nextjs_runtime(payload: NextjsRuntimeStartRequest) -> NextjsRuntimeStartResponse:
    try:
        result = start_nextjs_runtime(
            workspace_id=payload.workspace_id,
            site_id=payload.site_id,
            artifact_id=payload.artifact_id,
            deployment_id=payload.deployment_id,
            env_vars=payload.env_vars,
        )
    except NextjsRuntimeError as exc:
        return NextjsRuntimeStartResponse(success=False, error=str(exc), log_lines=exc.log_lines)

    return NextjsRuntimeStartResponse(
        success=True,
        container_name=result.container_name,
        healthy=result.healthy,
        status_code=result.status_code,
        log_lines=result.log_lines,
    )


@app.delete("/v1/nextjs-runtimes/{container_name}", dependencies=[Depends(require_shared_secret)])
def delete_nextjs_runtime(container_name: str) -> dict:
    try:
        stop_nextjs_runtime(container_name)
    except NextjsRuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return {"stopped": True}


@app.get(
    "/v1/nextjs-runtimes/{container_name}",
    response_model=NextjsRuntimeStatusResponse,
    dependencies=[Depends(require_shared_secret)],
)
def get_nextjs_runtime(container_name: str) -> NextjsRuntimeStatusResponse:
    return NextjsRuntimeStatusResponse(running=nextjs_is_running(container_name))
