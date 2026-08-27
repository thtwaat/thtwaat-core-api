"""Unit tests for app/static_sites/github_webhook.py — signature
verification and push-payload parsing for THTWAAT Deploy Phase 5C. No
network, no DB; the atomic delivery-id claim / branch-repository matching /
concurrency scenarios live in test_github_webhook_router.py (integration,
real Postgres) since they need a real unique constraint / real rows to be
meaningful."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.static_sites.github_webhook import (
    MalformedWebhookPayload,
    parse_push_event,
    verify_signature,
)

SECRET = "correct-horse-battery-staple-webhook-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _push_payload(**overrides):
    base = {
        "ref": "refs/heads/main",
        "after": "a" * 40,
        "deleted": False,
        "repository": {"id": 555, "name": "app", "owner": {"login": "octocat"}},
        "installation": {"id": 999},
        "sender": {"login": "octocat"},
    }
    base.update(overrides)
    return base


# ---- signature verification -------------------------------------------------


@pytest.mark.unit
def test_valid_signature_accepted():
    body = b'{"hello":"world"}'
    assert verify_signature(body, _sign(body), SECRET) is True


@pytest.mark.unit
def test_invalid_signature_rejected():
    body = b'{"hello":"world"}'
    bad_sig = "sha256=" + ("0" * 64)
    assert verify_signature(body, bad_sig, SECRET) is False


@pytest.mark.unit
def test_missing_signature_rejected():
    body = b'{"hello":"world"}'
    assert verify_signature(body, None, SECRET) is False
    assert verify_signature(body, "", SECRET) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "malformed",
    [
        "not-even-prefixed",
        "sha1=deadbeef",  # wrong algorithm prefix
        "sha256=",  # empty hex
        "sha256=not-hex-at-all!!",
        "sha256=zz" + "0" * 62,  # non-hex chars
    ],
)
def test_malformed_signature_header_rejected(malformed):
    body = b'{"hello":"world"}'
    assert verify_signature(body, malformed, SECRET) is False


@pytest.mark.unit
def test_wrong_secret_rejected():
    body = b'{"hello":"world"}'
    sig = _sign(body, secret=SECRET)
    assert verify_signature(body, sig, "a-completely-different-secret") is False


@pytest.mark.unit
def test_signature_is_over_exact_raw_bytes_not_reparsed_json():
    """Signing the JSON-decoded-then-reencoded body must NOT verify against
    a signature computed over the original bytes if whitespace/key order
    differs — proves we must sign/verify the raw body, never a
    re-serialization of it."""
    original = b'{"a":1,"b":2}'
    reencoded = json.dumps(json.loads(original)).encode("utf-8")  # default dumps adds spacing
    assert original != reencoded  # sanity: the two byte strings actually differ
    sig_over_original = _sign(original)
    assert verify_signature(reencoded, sig_over_original, SECRET) is False


@pytest.mark.unit
def test_no_secret_configured_never_verifies():
    body = b'{"hello":"world"}'
    sig = _sign(body, secret="")
    assert verify_signature(body, sig, "") is False


# ---- push payload parsing ---------------------------------------------------


@pytest.mark.unit
def test_parse_push_event_happy_path():
    event = parse_push_event(_push_payload())
    assert event.repository_id == "555"
    assert event.repository_owner == "octocat"
    assert event.repository_name == "app"
    assert event.installation_id == "999"
    assert event.branch == "main"
    assert event.commit_sha == "a" * 40
    assert event.deleted is False


@pytest.mark.unit
def test_parse_push_event_tag_push_has_no_branch():
    event = parse_push_event(_push_payload(ref="refs/tags/v1.0.0"))
    assert event.branch is None


@pytest.mark.unit
def test_parse_push_event_branch_deletion_flagged():
    event = parse_push_event(_push_payload(deleted=True, after="0" * 40))
    assert event.deleted is True


@pytest.mark.unit
def test_parse_push_event_zero_sha_treated_as_deletion_even_if_deleted_flag_missing():
    event = parse_push_event(_push_payload(deleted=False, after="0" * 40))
    assert event.deleted is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        "not-a-dict-at-all",
        123,
        None,
        [],
    ],
)
def test_parse_push_event_rejects_non_dict_payload(payload):
    with pytest.raises(MalformedWebhookPayload):
        parse_push_event(payload)


@pytest.mark.unit
def test_parse_push_event_rejects_missing_repository():
    payload = _push_payload()
    del payload["repository"]
    with pytest.raises(MalformedWebhookPayload):
        parse_push_event(payload)


@pytest.mark.unit
def test_parse_push_event_rejects_missing_repository_id():
    payload = _push_payload()
    payload["repository"] = {"name": "app", "owner": {"login": "octocat"}}
    with pytest.raises(MalformedWebhookPayload):
        parse_push_event(payload)


@pytest.mark.unit
def test_parse_push_event_rejects_missing_owner_or_name():
    payload = _push_payload()
    payload["repository"] = {"id": 1, "name": "", "owner": {"login": ""}}
    with pytest.raises(MalformedWebhookPayload):
        parse_push_event(payload)


@pytest.mark.unit
def test_parse_push_event_rejects_missing_ref():
    payload = _push_payload()
    del payload["ref"]
    with pytest.raises(MalformedWebhookPayload):
        parse_push_event(payload)


@pytest.mark.unit
def test_parse_push_event_rejects_missing_commit_sha():
    payload = _push_payload()
    del payload["after"]
    with pytest.raises(MalformedWebhookPayload):
        parse_push_event(payload)


@pytest.mark.unit
@pytest.mark.parametrize(
    "malicious_sha",
    [
        "'; DROP TABLE static_site_deployments; --",
        "$(rm -rf /)",
        "../../../etc/passwd",
        "not-hex-zzzz",
        "a" * 41,  # too long
        "abc",  # too short
        "",
    ],
)
def test_parse_push_event_rejects_malicious_or_malformed_commit_sha(malicious_sha):
    """A commit sha is interpolated into a GitHub API URL path and a
    filesystem path downstream (see github_client.fetch_repository_archive)
    — must be rejected here as malformed rather than reach either."""
    payload = _push_payload(after=malicious_sha)
    with pytest.raises(MalformedWebhookPayload):
        parse_push_event(payload)


@pytest.mark.unit
def test_parse_push_event_missing_installation_yields_none_not_error():
    payload = _push_payload()
    del payload["installation"]
    event = parse_push_event(payload)
    assert event.installation_id is None
