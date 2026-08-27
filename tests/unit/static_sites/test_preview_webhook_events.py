"""Unit tests for app/static_sites/github_webhook.py's THTWAAT Deploy Phase
6A addition — parse_pull_request_event(). Mirrors test_github_webhook.py's
style for parse_push_event; no network, no DB."""
from __future__ import annotations

import pytest

from app.static_sites.github_webhook import (
    MalformedWebhookPayload,
    SUPPORTED_PR_ACTIONS,
    parse_pull_request_event,
)

HEAD_SHA = "a" * 40


def _pr_payload(**overrides):
    base = {
        "action": "opened",
        "number": 42,
        "repository": {"id": 555, "name": "app", "owner": {"login": "octocat"}},
        "installation": {"id": 999},
        "pull_request": {
            "number": 42,
            "head": {"sha": HEAD_SHA, "ref": "feature-x", "repo": {"id": 555}},
            "base": {"ref": "main", "repo": {"id": 555}},
        },
        "sender": {"login": "octocat"},
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_supported_actions_constant():
    assert SUPPORTED_PR_ACTIONS == {"opened", "synchronize", "reopened", "closed"}


@pytest.mark.unit
def test_happy_path_same_repo_not_a_fork():
    event = parse_pull_request_event(_pr_payload())
    assert event.action == "opened"
    assert event.repository_id == "555"
    assert event.repository_owner == "octocat"
    assert event.repository_name == "app"
    assert event.installation_id == "999"
    assert event.pr_number == 42
    assert event.head_sha == HEAD_SHA
    assert event.head_ref == "feature-x"
    assert event.base_ref == "main"
    assert event.is_fork is False


@pytest.mark.unit
def test_fork_pr_detected_when_head_repo_id_differs():
    payload = _pr_payload()
    payload["pull_request"]["head"]["repo"] = {"id": 777}  # different repo id → fork
    event = parse_pull_request_event(payload)
    assert event.is_fork is True
    assert event.head_repository_id == "777"


@pytest.mark.unit
def test_fork_pr_detected_when_head_repo_deleted():
    """A fork PR whose source repo/fork has since been deleted has
    head.repo == null in GitHub's payload — must be treated as a fork too,
    never assumed same-repo when it can't be proven."""
    payload = _pr_payload()
    payload["pull_request"]["head"]["repo"] = None
    event = parse_pull_request_event(payload)
    assert event.is_fork is True
    assert event.head_repository_id is None


@pytest.mark.unit
@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened", "closed"])
def test_all_supported_actions_parse(action):
    event = parse_pull_request_event(_pr_payload(action=action))
    assert event.action == action


@pytest.mark.unit
def test_unsupported_action_still_parses_caller_filters():
    """parse_pull_request_event itself doesn't reject unsupported actions
    (edited/labeled/...) — that filtering is the router's job (see
    github_webhook_router.py), so an unsupported action must still parse
    cleanly rather than raise."""
    event = parse_pull_request_event(_pr_payload(action="labeled"))
    assert event.action == "labeled"
    assert event.action not in SUPPORTED_PR_ACTIONS


@pytest.mark.unit
def test_rejects_non_dict_payload():
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event("not-a-dict")


@pytest.mark.unit
def test_rejects_missing_action():
    payload = _pr_payload()
    del payload["action"]
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event(payload)


@pytest.mark.unit
def test_rejects_missing_repository():
    payload = _pr_payload()
    del payload["repository"]
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event(payload)


@pytest.mark.unit
def test_rejects_missing_pull_request():
    payload = _pr_payload()
    del payload["pull_request"]
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event(payload)


@pytest.mark.unit
def test_rejects_missing_pr_number():
    payload = _pr_payload()
    del payload["number"]
    payload["pull_request"].pop("number", None)
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event(payload)


@pytest.mark.unit
def test_rejects_missing_head_or_base():
    payload = _pr_payload()
    del payload["pull_request"]["head"]
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event(payload)


@pytest.mark.unit
@pytest.mark.parametrize(
    "malicious_sha",
    [
        "'; DROP TABLE static_site_preview_deployments; --",
        "$(rm -rf /)",
        "../../../etc/passwd",
        "not-hex-zzzz",
        "a" * 41,
        "abc",
        "",
    ],
)
def test_rejects_malicious_or_malformed_head_sha(malicious_sha):
    payload = _pr_payload()
    payload["pull_request"]["head"]["sha"] = malicious_sha
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event(payload)


@pytest.mark.unit
def test_rejects_missing_head_ref_or_base_ref():
    payload = _pr_payload()
    payload["pull_request"]["head"]["ref"] = ""
    with pytest.raises(MalformedWebhookPayload):
        parse_pull_request_event(payload)


@pytest.mark.unit
def test_missing_installation_yields_none_not_error():
    payload = _pr_payload()
    del payload["installation"]
    event = parse_pull_request_event(payload)
    assert event.installation_id is None


@pytest.mark.unit
def test_head_sha_is_lowercased():
    payload = _pr_payload()
    payload["pull_request"]["head"]["sha"] = HEAD_SHA.upper()
    event = parse_pull_request_event(payload)
    assert event.head_sha == HEAD_SHA
