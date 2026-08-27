"""THTWAAT Deploy Phase 5C — GitHub webhook signature verification + push
payload parsing.

Deliberately a standalone module (not inline in github_webhook_router.py)
so the security-critical HMAC comparison and payload extraction have their
own focused unit-test surface, mirroring how app/payments/webhooks/router.py
computes Razorpay's HMAC inline but THIS module exists because a THIRD
"never trust repository metadata before signature validation" concern (spec
§4) makes it worth separating "is this request from GitHub at all" from
"what does the payload say" as two distinct, independently testable steps.

Nothing in this module ever reads the request body as trusted before
``verify_signature`` has returned True — see github_webhook_router.py.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

_SIGNATURE_PREFIX = "sha256="
# Full 40-char commit SHA only — GitHub always sends the full SHA in push
# payloads; a short/malformed value is rejected rather than guessed at.
_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_BRANCH_REF_PREFIX = "refs/heads/"


def verify_signature(raw_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """Constant-time verification of GitHub's X-Hub-Signature-256 over the
    EXACT raw request body (never the re-serialized/parsed JSON — GitHub
    signs the bytes it sent, and any re-encoding can differ byte-for-byte).
    Returns False (never raises) on a missing header, a malformed header
    (not "sha256=<hex>"), or a mismatch — the caller maps every False to
    the same 401, so this never becomes an oracle for which failure mode
    occurred.
    """
    if not signature_header or not secret:
        return False
    if not signature_header.startswith(_SIGNATURE_PREFIX):
        return False
    provided_hex = signature_header[len(_SIGNATURE_PREFIX):].strip()
    if not provided_hex or not re.fullmatch(r"[0-9a-fA-F]+", provided_hex):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, provided_hex.lower())
    except (TypeError, ValueError):
        return False


class MalformedWebhookPayload(ValueError):
    """Raised when a SIGNATURE-VALID payload doesn't have the shape a push
    event requires — never raised before signature verification."""


@dataclass
class PushEvent:
    repository_id: str
    repository_owner: str
    repository_name: str
    installation_id: Optional[str]
    ref: str
    branch: Optional[str]  # None if ref isn't refs/heads/* (e.g. a tag push)
    commit_sha: str
    deleted: bool
    sender_login: Optional[str]


def parse_push_event(payload: Dict[str, Any]) -> PushEvent:
    """Extract only the fields THTWAAT Deploy needs from a GitHub `push`
    webhook payload, validating their shape. Raises MalformedWebhookPayload
    on anything missing/wrong-typed — the caller maps this to 400. Never
    trusts repository ownership/company scoping from this data alone; that
    cross-check happens separately against the stored GitHubConnection (see
    github_webhook_router.py) using repository_id + installation_id, not
    anything derived here.
    """
    if not isinstance(payload, dict):
        raise MalformedWebhookPayload("Webhook payload must be a JSON object")

    repository = payload.get("repository")
    if not isinstance(repository, dict):
        raise MalformedWebhookPayload("Missing repository")
    repository_id = repository.get("id")
    if repository_id is None:
        raise MalformedWebhookPayload("Missing repository.id")
    owner = ((repository.get("owner") or {}).get("login")) or ""
    name = repository.get("name") or ""
    if not owner or not name:
        raise MalformedWebhookPayload("Missing repository owner/name")

    installation = payload.get("installation")
    installation_id = None
    if isinstance(installation, dict) and installation.get("id") is not None:
        installation_id = str(installation["id"])

    ref = payload.get("ref")
    if not isinstance(ref, str) or not ref:
        raise MalformedWebhookPayload("Missing ref")
    branch = ref[len(_BRANCH_REF_PREFIX):] if ref.startswith(_BRANCH_REF_PREFIX) else None

    deleted = bool(payload.get("deleted", False))

    commit_sha = payload.get("after")
    if not isinstance(commit_sha, str):
        raise MalformedWebhookPayload("Missing after (commit sha)")
    commit_sha = commit_sha.strip().lower()
    # A branch DELETE push carries after == "0000...0000" (40 zeros) — never
    # treated as a real commit even if deleted weren't already set.
    is_zero_sha = commit_sha == "0" * 40
    if not is_zero_sha and not _COMMIT_SHA_PATTERN.match(commit_sha):
        raise MalformedWebhookPayload("Malformed commit sha")

    sender = payload.get("sender")
    sender_login = sender.get("login") if isinstance(sender, dict) else None

    return PushEvent(
        repository_id=str(repository_id),
        repository_owner=str(owner),
        repository_name=str(name),
        installation_id=installation_id,
        ref=ref,
        branch=branch,
        commit_sha=commit_sha,
        deleted=deleted or is_zero_sha,
        sender_login=sender_login,
    )


# ---- THTWAAT Deploy Phase 6A — pull_request event parsing -------------------

# Every other pull_request "action" (edited, assigned, labeled,
# review_requested, ...) never reaches preview-deployment logic — the
# webhook router acknowledges it and stops.
SUPPORTED_PR_ACTIONS = frozenset({"opened", "synchronize", "reopened", "closed"})


@dataclass
class PullRequestEvent:
    action: str
    repository_id: str
    repository_owner: str
    repository_name: str
    installation_id: Optional[str]
    pr_number: int
    head_sha: str
    head_ref: str  # source branch
    base_ref: str  # target branch — must equal the connection's selected_branch
    head_repository_id: Optional[str]  # for fork detection: differs from repository_id on a fork PR
    is_fork: bool
    sender_login: Optional[str]


def parse_pull_request_event(payload: Dict[str, Any]) -> PullRequestEvent:
    """Extract only the fields THTWAAT Deploy needs from a GitHub
    `pull_request` webhook payload. Mirrors parse_push_event's validation
    shape exactly. Never trusts repository ownership/company scoping from
    this data alone — that cross-check happens separately against the
    stored GitHubConnection using repository_id + installation_id, not
    anything derived here (see github_webhook_router.py)."""
    if not isinstance(payload, dict):
        raise MalformedWebhookPayload("Webhook payload must be a JSON object")

    action = payload.get("action")
    if not isinstance(action, str) or not action:
        raise MalformedWebhookPayload("Missing action")

    repository = payload.get("repository")
    if not isinstance(repository, dict):
        raise MalformedWebhookPayload("Missing repository")
    repository_id = repository.get("id")
    if repository_id is None:
        raise MalformedWebhookPayload("Missing repository.id")
    owner = ((repository.get("owner") or {}).get("login")) or ""
    name = repository.get("name") or ""
    if not owner or not name:
        raise MalformedWebhookPayload("Missing repository owner/name")

    installation = payload.get("installation")
    installation_id = None
    if isinstance(installation, dict) and installation.get("id") is not None:
        installation_id = str(installation["id"])

    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        raise MalformedWebhookPayload("Missing pull_request")

    pr_number = payload.get("number", pull_request.get("number"))
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number < 0:
        raise MalformedWebhookPayload("Missing or invalid pull_request number")

    head = pull_request.get("head")
    base = pull_request.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict):
        raise MalformedWebhookPayload("Missing pull_request.head/base")

    head_sha = head.get("sha")
    if not isinstance(head_sha, str):
        raise MalformedWebhookPayload("Missing pull_request.head.sha")
    head_sha = head_sha.strip().lower()
    if not _COMMIT_SHA_PATTERN.match(head_sha):
        raise MalformedWebhookPayload("Malformed pull_request.head.sha")

    head_ref = head.get("ref")
    base_ref = base.get("ref")
    if not isinstance(head_ref, str) or not head_ref or not isinstance(base_ref, str) or not base_ref:
        raise MalformedWebhookPayload("Missing pull_request.head.ref/base.ref")

    head_repo = head.get("repo")
    head_repository_id = None
    if isinstance(head_repo, dict) and head_repo.get("id") is not None:
        head_repository_id = str(head_repo["id"])
    # The top-level `repository` in a pull_request payload is always the
    # repo the webhook is configured on — i.e. the PR's base repository. A
    # fork PR's head repository has a different id; a missing/null
    # head.repo (source repo/fork deleted since the PR was opened) is
    # treated as a fork too — never assume same-repo when it can't be
    # proven.
    is_fork = head_repository_id is None or head_repository_id != str(repository_id)

    sender = payload.get("sender")
    sender_login = sender.get("login") if isinstance(sender, dict) else None

    return PullRequestEvent(
        action=action,
        repository_id=str(repository_id),
        repository_owner=str(owner),
        repository_name=str(name),
        installation_id=installation_id,
        pr_number=int(pr_number),
        head_sha=head_sha,
        head_ref=head_ref,
        base_ref=base_ref,
        head_repository_id=head_repository_id,
        is_fork=is_fork,
        sender_login=sender_login,
    )
