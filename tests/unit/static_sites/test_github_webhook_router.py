"""Integration tests for POST /api/v2/studio/static-sites/github/webhook —
THTWAAT Deploy Phase 5C. Real Postgres (db_session) + real app (client) +
real Redis (redis_client), exactly like test_github_state_security.py /
test_idempotency.py's real-stack tests: a mocked repo can't demonstrate an
actual unique-constraint race or a real cross-tenant query, so this is the
one file that proves those properties hold against the real database.

Requires: docker compose -f docker-compose.test.yml up -d db redis
(auto-skipped otherwise via the `integration_stack` fixture).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest

WEBHOOK_PATH = "/api/v2/studio/static-sites/github/webhook"
TEST_SECRET = "integration-test-webhook-secret-value"
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


def _sign(body: bytes, secret: str = TEST_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _push_body(*, repository_id: int, owner: str, name: str, installation_id: int,
                branch: str = "main", commit_sha: str = COMMIT_A, deleted: bool = False) -> bytes:
    payload = {
        "ref": f"refs/heads/{branch}",
        "after": commit_sha,
        "deleted": deleted,
        "repository": {"id": repository_id, "name": name, "owner": {"login": owner}},
        "installation": {"id": installation_id},
        "sender": {"login": owner},
    }
    return json.dumps(payload).encode("utf-8")


def _headers(body: bytes, *, event: str = "push", delivery: str = None, secret: str = TEST_SECRET, signed: bool = True):
    h = {"X-GitHub-Event": event, "Content-Type": "application/json"}
    if delivery is not None:
        h["X-GitHub-Delivery"] = delivery
    if signed:
        h["X-Hub-Signature-256"] = _sign(body, secret=secret)
    return h


@pytest.fixture
def webhook_secret(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "GITHUB_APP_WEBHOOK_SECRET", TEST_SECRET)
    return TEST_SECRET


@pytest.fixture
def company_and_site(db_session):
    from app.companies.model import Company
    from app.static_sites.models import StaticSite

    company = Company(id=uuid4(), slug=f"gh-webhook-{uuid4().hex[:8]}", name="GitHub Webhook Test Co")
    db_session.add(company)
    db_session.commit()

    site = StaticSite(id=uuid4(), workspace_id=company.id, name="Site", slug=f"site-{uuid4().hex[:8]}")
    db_session.add(site)
    db_session.commit()
    return company, site


def _connected(db_session, site, *, repository_id="555", installation_id="999", branch="main"):
    from app.static_sites.models import GitHubConnection

    conn = GitHubConnection(
        id=uuid4(), workspace_id=site.workspace_id, site_id=site.id,
        installation_id=installation_id, github_account_id="1", github_username="octocat",
        account_type="User", repository_owner="octocat", repository_name="app",
        repository_id=repository_id, default_branch="main", selected_branch=branch,
    )
    db_session.add(conn)
    db_session.commit()
    return conn


def _deployments_for_site(db_session, site_id):
    from app.static_sites.models import StaticSiteDeployment

    return (
        db_session.query(StaticSiteDeployment)
        .filter(StaticSiteDeployment.site_id == site_id)
        .order_by(StaticSiteDeployment.version.asc())
        .all()
    )


# ---- signature verification --------------------------------------------------


@pytest.mark.integration
def test_valid_signature_accepted_and_queues_deployment(client, db_session, webhook_secret, company_and_site, redis_client):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, commit_sha=COMMIT_A)

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    assert resp.status_code == 202
    data = resp.json()
    assert data["accepted"] is True
    deployment_id = data["deployment_id"]

    rows = _deployments_for_site(db_session, site.id)
    assert len(rows) == 1
    assert str(rows[0].id) == deployment_id
    assert rows[0].source_provider == "github"
    assert rows[0].github_commit_sha == COMMIT_A  # exact commit pinning
    assert rows[0].status == "queued"  # never built synchronously inside the webhook


@pytest.mark.integration
def test_invalid_signature_rejected(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    headers = _headers(body, delivery=str(uuid4()))
    headers["X-Hub-Signature-256"] = "sha256=" + ("0" * 64)

    resp = client.post(WEBHOOK_PATH, content=body, headers=headers)

    assert resp.status_code == 401
    assert _deployments_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_missing_signature_rejected(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999)

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4()), signed=False))

    assert resp.status_code == 401
    assert _deployments_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_malformed_signature_header_rejected(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    headers = _headers(body, delivery=str(uuid4()))
    headers["X-Hub-Signature-256"] = "not-even-hmac-shaped"

    resp = client.post(WEBHOOK_PATH, content=body, headers=headers)
    assert resp.status_code == 401


@pytest.mark.integration
def test_wrong_webhook_secret_rejected(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    headers = _headers(body, delivery=str(uuid4()), secret="a-totally-different-secret")

    resp = client.post(WEBHOOK_PATH, content=body, headers=headers)
    assert resp.status_code == 401


@pytest.mark.integration
def test_webhook_secret_never_appears_in_logs(client, db_session, webhook_secret, company_and_site, caplog):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    headers = _headers(body, delivery=str(uuid4()))
    headers["X-Hub-Signature-256"] = "sha256=" + ("0" * 64)

    with caplog.at_level("DEBUG"):
        client.post(WEBHOOK_PATH, content=body, headers=headers)

    for record in caplog.records:
        assert TEST_SECRET not in record.getMessage()


# ---- malformed payload --------------------------------------------------------


@pytest.mark.integration
def test_malformed_json_payload_rejected(client, webhook_secret):
    body = b"{not-valid-json"
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))
    assert resp.status_code == 400


@pytest.mark.integration
def test_malicious_commit_sha_rejected(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(
        repository_id=555, owner="octocat", name="app", installation_id=999,
        commit_sha="'; DROP TABLE static_site_deployments; --",
    )
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))
    assert resp.status_code == 400
    assert _deployments_for_site(db_session, site.id) == []


# ---- event filtering ------------------------------------------------------------


@pytest.mark.integration
def test_unsupported_event_type_ignored(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = json.dumps({"repository": {"id": 555}}).encode()
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, event="star", delivery=str(uuid4())))
    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _deployments_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_ping_event_acknowledged_without_side_effects(client, webhook_secret):
    body = json.dumps({"zen": "hello"}).encode()
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, event="ping", delivery=str(uuid4())))
    assert resp.status_code == 200
    assert resp.json().get("pong") is True


# ---- branch matching ------------------------------------------------------------


@pytest.mark.integration
def test_branch_mismatch_ignored(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site, branch="main")
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, branch="develop")

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _deployments_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_branch_deletion_never_deploys(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site, branch="main")
    body = _push_body(
        repository_id=555, owner="octocat", name="app", installation_id=999,
        branch="main", commit_sha="0" * 40, deleted=True,
    )

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _deployments_for_site(db_session, site.id) == []


# ---- repository matching / company isolation -------------------------------------


@pytest.mark.integration
def test_repository_not_connected_ignored(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    # No GitHubConnection created at all.
    body = _push_body(repository_id=999999, owner="nobody", name="nothing", installation_id=1)

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True


@pytest.mark.integration
def test_repository_id_mismatch_rejected_even_with_matching_name(client, db_session, webhook_secret, company_and_site):
    """Same owner/name text but a DIFFERENT repository_id must never match
    — proves matching is by GitHub's stable id, never the display name."""
    company, site = company_and_site
    _connected(db_session, site, repository_id="555", installation_id="999")
    body = _push_body(repository_id=666, owner="octocat", name="app", installation_id=999)

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _deployments_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_company_isolation_webhook_for_company_a_never_deploys_company_b(client, db_session, webhook_secret, company_and_site):
    from app.companies.model import Company
    from app.static_sites.models import StaticSite

    company_a, site_a = company_and_site
    _connected(db_session, site_a, repository_id="111", installation_id="1")

    company_b = Company(id=uuid4(), slug=f"gh-webhook-b-{uuid4().hex[:8]}", name="Company B")
    db_session.add(company_b)
    db_session.commit()
    site_b = StaticSite(id=uuid4(), workspace_id=company_b.id, name="Site B", slug=f"site-b-{uuid4().hex[:8]}")
    db_session.add(site_b)
    db_session.commit()
    _connected(db_session, site_b, repository_id="222", installation_id="2")

    # Push for company B's repository.
    body = _push_body(repository_id=222, owner="octocat", name="appb", installation_id=2)
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    assert resp.status_code == 202
    assert _deployments_for_site(db_session, site_a.id) == [], "company A's site must never be touched by company B's push"
    assert len(_deployments_for_site(db_session, site_b.id)) == 1


# ---- idempotency / duplicates -----------------------------------------------------


@pytest.mark.integration
def test_duplicate_github_delivery_id_creates_only_one_deployment(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, commit_sha=COMMIT_A)
    delivery_id = str(uuid4())

    resp1 = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=delivery_id))
    resp2 = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=delivery_id))

    assert resp1.status_code == 202
    assert resp1.json().get("duplicate") is not True
    assert resp2.status_code == 202
    assert resp2.json().get("duplicate") is True
    assert len(_deployments_for_site(db_session, site.id)) == 1


@pytest.mark.integration
def test_duplicate_same_commit_different_delivery_ids_does_not_redeploy(client, db_session, webhook_secret, company_and_site):
    """A distinct webhook delivery (its own delivery id — e.g. a GitHub
    'Redeliver') carrying the exact same commit+branch this site is already
    on must not launch a second build."""
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, commit_sha=COMMIT_A)

    resp1 = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))
    resp2 = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp2.json().get("duplicate") is True
    assert len(_deployments_for_site(db_session, site.id)) == 1


@pytest.mark.integration
def test_concurrent_pushes_create_distinct_versioned_deployments(client, db_session, webhook_secret, company_and_site):
    """Two different commits pushed back-to-back must each get their own
    deployment row pinned to their own commit — never merged/overwritten."""
    company, site = company_and_site
    _connected(db_session, site)
    body_a = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, commit_sha=COMMIT_A)
    body_b = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, commit_sha=COMMIT_B)

    resp_a = client.post(WEBHOOK_PATH, content=body_a, headers=_headers(body_a, delivery=str(uuid4())))
    resp_b = client.post(WEBHOOK_PATH, content=body_b, headers=_headers(body_b, delivery=str(uuid4())))

    assert resp_a.status_code == 202
    assert resp_b.status_code == 202
    rows = _deployments_for_site(db_session, site.id)
    assert len(rows) == 2
    assert rows[0].github_commit_sha == COMMIT_A
    assert rows[1].github_commit_sha == COMMIT_B
    assert rows[1].version > rows[0].version
    assert rows[1].is_current is True
    assert rows[0].is_current is False


# ---- queue / worker handoff --------------------------------------------------------


@pytest.mark.integration
def test_worker_job_enqueued_with_deployment_id(client, db_session, webhook_secret, company_and_site, redis_client):
    # Deliberately NOT the file's shared default repository_id="555"/
    # installation_id="999" — db_session commits are never rolled back
    # between tests (see tests/conftest.py), so every other test in this
    # file that uses the default leaves its own GitHubConnection row
    # sitting in the same table. list_github_connections_by_repository()
    # (repository.py) now correctly fans out over ALL of them, so reusing
    # the shared default here would make this test's single-job assertion
    # depend on how many earlier tests already ran — a distinct id keeps
    # this test's fan-out set to exactly one connection.
    company, site = company_and_site
    _connected(db_session, site, repository_id="556", installation_id="1000")
    body = _push_body(repository_id=556, owner="octocat", name="app", installation_id=1000, commit_sha=COMMIT_A)

    redis_client.delete("thtwaat:jobs")
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))
    deployment_id = resp.json()["deployment_id"]

    raw = redis_client.rpop("thtwaat:jobs")
    assert raw is not None, "the webhook must enqueue a job onto thtwaat:jobs, not run the build inline"
    job = json.loads(raw)
    assert job["type"] == "static_site.github_deploy"
    assert job["deployment_id"] == deployment_id


@pytest.mark.integration
def test_webhook_responds_fast_without_running_the_build_inline(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, commit_sha=COMMIT_A)

    started = time.perf_counter()
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))
    elapsed = time.perf_counter() - started

    assert resp.status_code == 202
    assert elapsed < 5.0, "the webhook handler must return fast — no clone/build/publish inline"
    rows = _deployments_for_site(db_session, site.id)
    assert rows[0].status == "queued"


# ---- no credential ever leaks in the response --------------------------------------


@pytest.mark.integration
def test_response_never_contains_installation_token_or_secret(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _push_body(repository_id=555, owner="octocat", name="app", installation_id=999, commit_sha=COMMIT_A)

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=str(uuid4())))

    dumped = resp.text
    assert TEST_SECRET not in dumped
    assert "ghs_" not in dumped  # GitHub installation token prefix
