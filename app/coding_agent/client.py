"""
app/coding_agent/client.py — Phase 6C-2: thin HTTP client for calling the
separately-deployed AI_Project AgentRuntime's /service/* endpoints.

Mirrors app.static_sites.vite_build.py's own established pattern for
calling an external, shared-secret-authenticated service over HTTP
(plain, synchronous httpx.request() with an explicit timeout, translated
errors, never the raw upstream response body surfaced to the caller) —
not a new networking convention.

Every call mints a FRESH, short-lived service token
(app.coding_agent.service.mint_service_token) — never a cached/reused
one — so the token's exp window only ever needs to cover a single
request's round trip.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

import httpx

from app.coding_agent.service import mint_service_token
from app.config.settings import settings

logger = logging.getLogger(__name__)


class CodingAgentError(Exception):
    """Domain error for anything that goes wrong talking to AI_Project —
    transport failure, an upstream error status, or an upstream response
    this client can't make sense of. Carries only a status_code + a
    message ALREADY safe to show a caller (never the raw upstream body,
    which could carry AI_Project-internal detail); app.coding_agent.
    router translates this into the actual HTTPException."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _base_url() -> str:
    base = (settings.CODING_AGENT_API_BASE_URL or "").rstrip("/")
    if not base:
        raise CodingAgentError(503, "Coding Agent integration is not configured on this server.")
    return base


def _headers(*, company_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, str]:
    token = mint_service_token(company_id=company_id, user_id=user_id)
    return {"Authorization": f"Bearer {token.access_token}"}


def _request(
    method: str, path: str, *, company_id: uuid.UUID, user_id: uuid.UUID, json_body: Optional[dict] = None,
) -> httpx.Response:
    url = _base_url() + path
    headers = _headers(company_id=company_id, user_id=user_id)
    try:
        return httpx.request(
            method, url, json=json_body, headers=headers,
            timeout=settings.CODING_AGENT_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        raise CodingAgentError(504, "Coding Agent service timed out.") from None
    except httpx.HTTPError:
        logger.error("coding_agent_transport_error method=%s path=%s", method, path)
        raise CodingAgentError(502, "Coding Agent service is not reachable.") from None


def _handle_response(resp: httpx.Response) -> Dict[str, Any]:
    if resp.status_code in (200, 201):
        return resp.json()
    if resp.status_code == 404:
        raise CodingAgentError(404, "Coding task not found.")
    if resp.status_code == 400:
        raise CodingAgentError(400, "Invalid coding task request.")
    if resp.status_code == 409:
        raise CodingAgentError(409, "This request is already being processed.")
    # 401/403 here means CORE'S OWN token/scope is wrong (a
    # misconfiguration on this server), and 5xx is an upstream failure —
    # neither is the calling user's fault and neither ever echoes
    # AI_Project's own response body (could carry internal detail).
    logger.error("coding_agent_upstream_error status=%s", resp.status_code)
    raise CodingAgentError(502, "Coding Agent service error.")


def ensure_link(*, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
    resp = _request("POST", "/service/link", company_id=company_id, user_id=user_id)
    _handle_response(resp)


def create_task(
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    goal: str,
    idempotency_key: str,
    budget: Optional[dict] = None,
    context_limits: Optional[dict] = None,
) -> Dict[str, Any]:
    # Auto-provisions the workspace mapping first (idempotent on
    # AI_Project's side — see api.service_link_store.ensure_link) so a
    # first-time caller "just works" without a separate provisioning
    # step; AI_Project's own /service/tasks endpoint still independently
    # requires the mapping to already exist and never creates one
    # itself, keeping that invariant enforced at its own boundary too.
    ensure_link(company_id=company_id, user_id=user_id)

    body: Dict[str, Any] = {"goal": goal, "idempotency_key": idempotency_key}
    if budget:
        body["budget"] = budget
    if context_limits:
        body["context_limits"] = context_limits
    resp = _request("POST", "/service/tasks", company_id=company_id, user_id=user_id, json_body=body)
    return _handle_response(resp)


def get_task(*, company_id: uuid.UUID, user_id: uuid.UUID, task_id: str) -> Dict[str, Any]:
    resp = _request("GET", f"/service/tasks/{task_id}", company_id=company_id, user_id=user_id)
    return _handle_response(resp)


def cancel_task(*, company_id: uuid.UUID, user_id: uuid.UUID, task_id: str) -> Dict[str, Any]:
    resp = _request("POST", f"/service/tasks/{task_id}/cancel", company_id=company_id, user_id=user_id)
    return _handle_response(resp)
