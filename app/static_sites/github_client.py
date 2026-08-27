"""THTWAAT Deploy Phase 5 — GitHub App API client.

GitHub App, not OAuth App (see app/static_sites/models.py::GitHubConnection
docstring): the app authenticates itself with an RS256 JWT signed by
``settings.GITHUB_APP_PRIVATE_KEY`` (app_jwt) to mint short-lived
installation access tokens on demand. No GitHub user access/refresh token
is ever requested, returned, logged, or persisted anywhere in this module.

Every request here targets a hardcoded ``GITHUB_API_BASE`` — this module
never accepts a URL, host, or path from a caller. ``owner``/``repo`` values
are validated with ``_validate_path_segment`` before being interpolated
into a request path, closing path-traversal/header-injection/SSRF via
crafted repository names.
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException, status
from jose import jwt

from app.config.settings import settings

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_INSTALL_BASE = "https://github.com"
_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_TIMEOUT = 20.0
# Path-segment values only (repo owner/name) — never a full URL/host. GitHub
# usernames/org names/repo names are alnum, hyphen, underscore, or dot.
_PATH_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class GitHubApiError(HTTPException):
    """Raised on any GitHub API failure. detail is always a fixed, generic,
    safe-to-return message — never the raw GitHub response body, a token, or
    the app private key."""


def app_configured() -> bool:
    return bool(
        (settings.GITHUB_APP_ID or "").strip()
        and (settings.GITHUB_APP_SLUG or "").strip()
        and (settings.GITHUB_APP_PRIVATE_KEY or "").strip()
    )


def require_app_configured() -> None:
    if not app_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration is not configured",
        )


def new_state() -> str:
    return secrets.token_urlsafe(32)


def hash_state(raw_state: str) -> str:
    return hashlib.sha256(raw_state.encode("utf-8")).hexdigest()


def build_installation_url(*, state: str) -> str:
    require_app_configured()
    slug = settings.GITHUB_APP_SLUG.strip()
    return f"{GITHUB_INSTALL_BASE}/apps/{slug}/installations/new?state={quote(state)}"


def validate_path_segment(value: str, *, field: str) -> str:
    v = (value or "").strip()
    if not _PATH_SEGMENT_PATTERN.match(v):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field}",
        )
    return v


# Full git commit SHA only (7-40 lowercase hex) — THTWAAT Deploy Phase 5C
# pins every auto-deploy to the exact commit GitHub reported, never a moving
# ref like "main"/"latest" or an uppercase/short-form value that could be
# ambiguous. Interpolated into a GitHub API URL path, so this is also the
# thing that closes path-traversal/SSRF via a crafted "sha".
_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")


def validate_commit_sha(value: str) -> str:
    v = (value or "").strip().lower()
    if not _COMMIT_SHA_PATTERN.match(v):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid commit SHA")
    return v


def _app_jwt() -> str:
    require_app_configured()
    now = int(time.time())
    claims = {
        # 60s clock-drift tolerance backward; GitHub caps exp at 10 minutes.
        "iat": now - 60,
        "exp": now + 540,
        "iss": settings.GITHUB_APP_ID.strip(),
    }
    try:
        return jwt.encode(claims, settings.GITHUB_APP_PRIVATE_KEY, algorithm="RS256")
    except Exception as exc:  # noqa: BLE001
        # Never log the private key or exception args (may embed key material).
        logger.error("github_app_jwt_sign_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration is unavailable: invalid app credentials.",
        ) from exc


def _handle_response(resp: httpx.Response) -> Any:
    if resp.status_code == 429 or resp.headers.get("x-ratelimit-remaining") == "0":
        raise GitHubApiError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="GitHub API rate limit exceeded. Try again later.",
        )
    if resp.status_code in (401, 403):
        raise GitHubApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GitHub access is missing or was revoked. Please reconnect.",
        )
    if resp.status_code == 404:
        raise GitHubApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub resource not found or not accessible.",
        )
    if resp.status_code >= 500:
        raise GitHubApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub is temporarily unavailable.",
        )
    if resp.status_code >= 400:
        raise GitHubApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub rejected the request.",
        )
    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        raise GitHubApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub returned an unexpected response.",
        ) from exc


async def _get(url: str, *, token: str) -> Any:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                url, headers={**_API_HEADERS, "Authorization": f"Bearer {token}"}
            )
    except httpx.RequestError as exc:
        logger.warning("github_api_request_failed url=%s", url)
        raise GitHubApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub is temporarily unavailable.",
        ) from exc
    return _handle_response(resp)


async def _post(url: str, *, token: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                url, headers={**_API_HEADERS, "Authorization": f"Bearer {token}"}
            )
    except httpx.RequestError as exc:
        logger.warning("github_api_request_failed url=%s", url)
        raise GitHubApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub is temporarily unavailable.",
        ) from exc
    return _handle_response(resp)


async def get_installation(installation_id: str) -> Dict[str, Any]:
    """App-level auth (not an installation token) — used once at callback
    time to resolve which GitHub account installed the app."""
    token = _app_jwt()
    return await _get(f"{GITHUB_API_BASE}/app/installations/{quote(str(installation_id))}", token=token)


async def mint_installation_token(installation_id: str) -> str:
    """Short-lived (~1h) installation access token — minted fresh for the
    caller's immediate use and never persisted or logged."""
    token = _app_jwt()
    data = await _post(
        f"{GITHUB_API_BASE}/app/installations/{quote(str(installation_id))}/access_tokens",
        token=token,
    )
    installation_token = data.get("token")
    if not installation_token:
        raise GitHubApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub did not return an installation token.",
        )
    return installation_token


async def get_repository(installation_token: str, owner: str, repo: str) -> Dict[str, Any]:
    owner = validate_path_segment(owner, field="repository owner")
    repo = validate_path_segment(repo, field="repository name")
    return await _get(
        f"{GITHUB_API_BASE}/repos/{quote(owner)}/{quote(repo)}", token=installation_token
    )


async def list_installation_repositories(
    installation_token: str, *, page: int = 1, per_page: int = 30
) -> Dict[str, Any]:
    page = max(1, int(page))
    per_page = max(1, min(100, int(per_page)))
    return await _get(
        f"{GITHUB_API_BASE}/installation/repositories?page={page}&per_page={per_page}",
        token=installation_token,
    )


async def get_branch(
    installation_token: str, owner: str, repo: str, branch: str
) -> Dict[str, Any]:
    """Existence check for one branch — used by select_repository to verify
    the requested branch actually exists before persisting the selection,
    without depending on pagination across list_branches."""
    owner = validate_path_segment(owner, field="repository owner")
    repo = validate_path_segment(repo, field="repository name")
    branch = (branch or "").strip()
    if not branch or len(branch) > 255 or "\x00" in branch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid branch name")
    return await _get(
        f"{GITHUB_API_BASE}/repos/{quote(owner)}/{quote(repo)}/branches/{quote(branch)}",
        token=installation_token,
    )


async def list_branches(
    installation_token: str, owner: str, repo: str, *, page: int = 1, per_page: int = 30
) -> List[Dict[str, Any]]:
    owner = validate_path_segment(owner, field="repository owner")
    repo = validate_path_segment(repo, field="repository name")
    page = max(1, int(page))
    per_page = max(1, min(100, int(per_page)))
    result = await _get(
        f"{GITHUB_API_BASE}/repos/{quote(owner)}/{quote(repo)}/branches?page={page}&per_page={per_page}",
        token=installation_token,
    )
    # GitHub returns a bare list for this endpoint, not an object.
    if isinstance(result, list):
        return result
    return []


async def fetch_repository_archive(
    installation_token: str,
    owner: str,
    repo: str,
    commit_sha: str,
    *,
    dest_path: "Path",
    max_bytes: Optional[int] = None,
) -> int:
    """Stream GitHub's zipball for one exact, already-validated commit SHA to
    dest_path (a server-generated temp path — never anything derived from
    request input). Deliberately takes owner/repo/a full commit SHA, never a
    branch name or "latest"/"HEAD" — THTWAAT Deploy Phase 5C pins every
    auto-deploy to the exact commit GitHub's webhook reported, and a zipball
    fetched by SHA is immutable (a zipball fetched by branch name would be
    whatever the branch points to AT FETCH TIME, which can have moved again
    since the webhook fired).

    Enforces max_bytes while streaming (never after buffering the whole
    response in memory) so a huge/hostile repository can't exhaust disk on
    the box performing the fetch. Returns the number of bytes written.
    """
    from app.config.settings import settings as _settings

    owner = validate_path_segment(owner, field="repository owner")
    repo = validate_path_segment(repo, field="repository name")
    commit_sha = validate_commit_sha(commit_sha)
    cap = int(max_bytes if max_bytes is not None else getattr(_settings, "GITHUB_ARCHIVE_MAX_BYTES", 50 * 1024 * 1024))

    url = f"{GITHUB_API_BASE}/repos/{quote(owner)}/{quote(repo)}/zipball/{quote(commit_sha)}"
    written = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as client:
            async with client.stream(
                "GET", url, headers={**_API_HEADERS, "Authorization": f"Bearer {installation_token}"}
            ) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    _handle_response(resp)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        written += len(chunk)
                        if written > cap:
                            fh.close()
                            dest_path.unlink(missing_ok=True)
                            raise GitHubApiError(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Repository archive exceeds the {cap} byte limit.",
                            )
                        fh.write(chunk)
    except httpx.RequestError as exc:
        logger.warning("github_archive_fetch_failed owner=%s repo=%s", owner, repo)
        dest_path.unlink(missing_ok=True)
        raise GitHubApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub is temporarily unavailable.",
        ) from exc
    if written == 0:
        dest_path.unlink(missing_ok=True)
        raise GitHubApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub returned an empty repository archive.",
        )
    return written
