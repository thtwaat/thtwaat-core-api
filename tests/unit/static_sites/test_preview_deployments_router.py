"""Integration tests for THTWAAT Deploy Phase 6A Preview Deployments —
POST /api/v2/studio/static-sites/github/webhook's pull_request handling,
plus the authenticated GET/DELETE /previews endpoints. Real Postgres
(db_session) + real app (client) + real Redis (redis_client), mirroring
test_github_webhook_router.py's real-stack style: a mocked repo can't
demonstrate an actual unique-constraint race or a real cross-tenant query.

Requires: docker compose -f docker-compose.test.yml up -d db redis
(auto-skipped otherwise via the `integration_stack` fixture).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest

WEBHOOK_PATH = "/api/v2/studio/static-sites/github/webhook"
TEST_SECRET = "integration-test-webhook-secret-value"
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


def _sign(body: bytes, secret: str = TEST_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _pr_body(
    *, repository_id: int, owner: str, name: str, installation_id: int, pr_number: int = 7,
    action: str = "opened", head_sha: str = COMMIT_A, head_ref: str = "feature-x", base_ref: str = "main",
    head_repository_id: int | None = None,
) -> bytes:
    payload = {
        "action": action,
        "number": pr_number,
        "repository": {"id": repository_id, "name": name, "owner": {"login": owner}},
        "installation": {"id": installation_id},
        "pull_request": {
            "number": pr_number,
            "head": {
                "sha": head_sha, "ref": head_ref,
                "repo": {"id": head_repository_id if head_repository_id is not None else repository_id},
            },
            "base": {"ref": base_ref, "repo": {"id": repository_id}},
        },
        "sender": {"login": owner},
    }
    return json.dumps(payload).encode("utf-8")


def _headers(body: bytes, *, delivery: str = None, secret: str = TEST_SECRET):
    return {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery or str(uuid4()),
        "X-Hub-Signature-256": _sign(body, secret=secret),
        "Content-Type": "application/json",
    }


@pytest.fixture
def webhook_secret(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "GITHUB_APP_WEBHOOK_SECRET", TEST_SECRET)
    return TEST_SECRET


@pytest.fixture
def company_and_site(db_session):
    from app.companies.model import Company
    from app.static_sites.models import StaticSite

    company = Company(id=uuid4(), slug=f"preview-test-{uuid4().hex[:8]}", name="Preview Test Co")
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


def _previews_for_site(db_session, site_id):
    from app.static_sites.models import StaticSitePreviewDeployment

    return (
        db_session.query(StaticSitePreviewDeployment)
        .filter(StaticSitePreviewDeployment.site_id == site_id)
        .all()
    )


def _admin_headers(db_session, company):
    """Mint a real bearer token for an owner/admin user of `company` so the
    authenticated /previews endpoints (RBAC-gated) can be exercised. Mirrors
    how get_current_user_profile() actually resolves a token: the JWT only
    carries `sub` (user id) — role/company_id are read server-side from the
    DB row, never trusted from token claims."""
    from app.auth.service import AuthService
    from app.rbac.enums import EnterpriseRole
    from app.users.model import User, UserStatus

    user = User(
        id=uuid4(), company_id=company.id, email=f"admin-{uuid4().hex[:8]}@example.com",
        hashed_password="x", first_name="Test", last_name="Admin",
        role=EnterpriseRole.ADMIN, status=UserStatus.ACTIVE, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = AuthService(db_session).create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}, user


# ---- lifecycle: opened / synchronize / reopened / closed --------------------


@pytest.mark.integration
def test_pr_opened_creates_preview_and_enqueues_job(client, db_session, webhook_secret, company_and_site, redis_client):
    company, site = company_and_site
    _connected(db_session, site)
    redis_client.delete("thtwaat:jobs")
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999, action="opened")

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    assert resp.status_code == 202
    rows = _previews_for_site(db_session, site.id)
    assert len(rows) == 1
    assert rows[0].pr_number == 7
    assert rows[0].commit_sha == COMMIT_A
    assert rows[0].generation == 1
    assert rows[0].status == "queued"  # never built synchronously inside the webhook
    assert rows[0].hostname and rows[0].hostname.startswith("pr-7-")

    raw = redis_client.rpop("thtwaat:jobs")
    assert raw is not None
    job = json.loads(raw)
    assert job["type"] == "static_site.preview_deploy"
    assert job["preview_id"] == str(rows[0].id)
    assert job["generation"] == 1


@pytest.mark.integration
def test_pr_synchronize_advances_same_row_not_a_new_one(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    opened = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999, action="opened")
    client.post(WEBHOOK_PATH, content=opened, headers=_headers(opened))
    first_id = _previews_for_site(db_session, site.id)[0].id

    sync = _pr_body(
        repository_id=555, owner="octocat", name="app", installation_id=999,
        action="synchronize", head_sha=COMMIT_B,
    )
    resp = client.post(WEBHOOK_PATH, content=sync, headers=_headers(sync))

    assert resp.status_code == 202
    rows = _previews_for_site(db_session, site.id)
    assert len(rows) == 1  # UniqueConstraint(site_id, pr_number) — updated in place
    assert rows[0].id == first_id
    assert rows[0].commit_sha == COMMIT_B
    assert rows[0].generation == 2


@pytest.mark.integration
def test_pr_closed_enqueues_teardown_and_reopened_resurrects_same_row(
    client, db_session, webhook_secret, company_and_site, redis_client
):
    # Deliberately NOT the file's shared default repository_id="555"/
    # installation_id="999"/pr_number=7 — db_session commits are never
    # rolled back between tests (see tests/conftest.py), so every other
    # test in this file that uses the default leaves its own
    # GitHubConnection (and often its own open preview for PR #7) sitting
    # in the same tables. list_github_connections_by_repository()
    # (repository.py) now correctly fans out over every matching
    # connection, so reusing the shared default here would make this
    # test's single-job/single-row assertions depend on which earlier
    # tests already ran. A distinct id+PR number keeps this test's fan-out
    # set to exactly its own site.
    company, site = company_and_site
    _connected(db_session, site, repository_id="557", installation_id="1001")
    opened = _pr_body(
        repository_id=557, owner="octocat", name="app", installation_id=1001, action="opened", pr_number=5557,
    )
    client.post(WEBHOOK_PATH, content=opened, headers=_headers(opened))
    original_id = _previews_for_site(db_session, site.id)[0].id
    original_hostname = _previews_for_site(db_session, site.id)[0].hostname

    redis_client.delete("thtwaat:jobs")
    closed = _pr_body(
        repository_id=557, owner="octocat", name="app", installation_id=1001, action="closed", pr_number=5557,
    )
    resp = client.post(WEBHOOK_PATH, content=closed, headers=_headers(closed))
    assert resp.status_code == 202
    raw = redis_client.rpop("thtwaat:jobs")
    assert raw is not None
    job = json.loads(raw)
    assert job["type"] == "static_site.preview_teardown"
    assert job["preview_id"] == str(original_id)

    # Simulate the worker actually running the teardown job before reopen.
    from app.static_sites.preview_service import PreviewDeploymentService

    PreviewDeploymentService(db_session).teardown(original_id, reason="pr_closed")
    db_session.expire_all()
    torn_down = _previews_for_site(db_session, site.id)[0]
    assert torn_down.status == "torn_down"
    assert torn_down.torn_down_at is not None

    reopened = _pr_body(
        repository_id=557, owner="octocat", name="app", installation_id=1001,
        action="reopened", head_sha=COMMIT_B, pr_number=5557,
    )
    resp = client.post(WEBHOOK_PATH, content=reopened, headers=_headers(reopened))
    assert resp.status_code == 202
    # The webhook request handled this through the app's OWN DB session (a
    # different connection than this test's db_session — see get_db()); the
    # preview row this test already loaded above (`torn_down`) is still
    # sitting in db_session's identity map with its pre-webhook attributes,
    # so it must be expired before re-querying or SQLAlchemy will silently
    # hand back the stale, already-loaded object instead of re-reading it.
    db_session.expire_all()
    rows = _previews_for_site(db_session, site.id)
    assert len(rows) == 1
    assert rows[0].id == original_id  # SAME row resurrected, not a new one
    assert rows[0].torn_down_at is None
    assert rows[0].hostname == original_hostname  # SAME hostname reused


@pytest.mark.integration
def test_pr_closed_with_no_active_preview_ignored(client, db_session, webhook_secret, company_and_site):
    # Distinct repository_id/installation_id/pr_number — see the comment on
    # test_pr_closed_enqueues_teardown_and_reopened_resurrects_same_row
    # above: other tests in this file leave an open PR #7 preview under the
    # shared default id, which list_github_connections_by_repository()'s
    # fan-out would otherwise legitimately (and correctly) also match here.
    company, site = company_and_site
    _connected(db_session, site, repository_id="558", installation_id="1002")
    body = _pr_body(
        repository_id=558, owner="octocat", name="app", installation_id=1002, action="closed", pr_number=5558,
    )

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _previews_for_site(db_session, site.id) == []


# ---- security: fork rejection, base-branch matching, repository confusion ----


@pytest.mark.integration
def test_fork_pr_rejected_by_default(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _pr_body(
        repository_id=555, owner="octocat", name="app", installation_id=999,
        head_repository_id=999999,  # different repo id → fork
    )

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert resp.json()["reason"] == "fork_pr_rejected"
    assert _previews_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_base_branch_mismatch_ignored(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site, branch="main")
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999, base_ref="develop")

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _previews_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_repository_id_mismatch_rejected_even_with_matching_name(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site, repository_id="555", installation_id="999")
    body = _pr_body(
        repository_id=666, owner="octocat", name="app", installation_id=999, head_repository_id=666
    )

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _previews_for_site(db_session, site.id) == []


@pytest.mark.integration
def test_company_isolation_pr_webhook_never_creates_preview_under_wrong_company(
    client, db_session, webhook_secret, company_and_site
):
    from app.companies.model import Company
    from app.static_sites.models import StaticSite

    company_a, site_a = company_and_site
    _connected(db_session, site_a, repository_id="111", installation_id="1")

    company_b = Company(id=uuid4(), slug=f"preview-b-{uuid4().hex[:8]}", name="Company B")
    db_session.add(company_b)
    db_session.commit()
    site_b = StaticSite(id=uuid4(), workspace_id=company_b.id, name="Site B", slug=f"site-b-{uuid4().hex[:8]}")
    db_session.add(site_b)
    db_session.commit()
    _connected(db_session, site_b, repository_id="222", installation_id="2")

    body = _pr_body(
        repository_id=222, owner="octocat", name="appb", installation_id=2, head_repository_id=222
    )
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    assert resp.status_code == 202
    assert _previews_for_site(db_session, site_a.id) == []
    assert len(_previews_for_site(db_session, site_b.id)) == 1


# ---- idempotency --------------------------------------------------------------


@pytest.mark.integration
def test_duplicate_delivery_id_creates_only_one_preview(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    delivery_id = str(uuid4())

    resp1 = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=delivery_id))
    resp2 = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, delivery=delivery_id))

    assert resp1.status_code == 202
    assert resp2.json().get("duplicate") is True
    assert len(_previews_for_site(db_session, site.id)) == 1


@pytest.mark.integration
def test_unsupported_pr_action_ignored(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999, action="labeled")

    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    assert resp.status_code == 200
    assert resp.json()["ignored"] is True
    assert _previews_for_site(db_session, site.id) == []


# ---- billing / quota ------------------------------------------------------------


@pytest.mark.integration
def test_quota_exceeded_ignores_delivery_and_creates_no_row(client, db_session, webhook_secret, company_and_site):
    from app.companies.model import CompanyPlan

    company, site = company_and_site
    company.plan = CompanyPlan.FREE  # max_preview_deployments == 1
    db_session.add(company)
    db_session.commit()
    _connected(db_session, site)

    # First PR consumes the FREE plan's one preview slot.
    first = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999, pr_number=1)
    resp1 = client.post(WEBHOOK_PATH, content=first, headers=_headers(first))
    assert resp1.status_code == 202

    # A second, DIFFERENT PR must be quota-blocked (never a raw 429 to GitHub).
    second = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999, pr_number=2)
    resp2 = client.post(WEBHOOK_PATH, content=second, headers=_headers(second))

    assert resp2.status_code == 200
    assert resp2.json()["ignored"] is True
    assert resp2.json()["reason"] == "quota_exceeded"
    rows = _previews_for_site(db_session, site.id)
    assert len(rows) == 1  # only the first PR got a preview


# ---- exact commit pinning -----------------------------------------------------


@pytest.mark.integration
def test_exact_commit_sha_pinned(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999, head_sha=COMMIT_B)

    client.post(WEBHOOK_PATH, content=body, headers=_headers(body))

    rows = _previews_for_site(db_session, site.id)
    assert rows[0].commit_sha == COMMIT_B


# ---- authenticated preview API (list/get/close) --------------------------------


@pytest.mark.integration
def test_authenticated_list_and_get_previews(client, db_session, webhook_secret, company_and_site):
    company, site = company_and_site
    _connected(db_session, site)
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    client.post(WEBHOOK_PATH, content=body, headers=_headers(body))
    preview_id = str(_previews_for_site(db_session, site.id)[0].id)

    headers, _user = _admin_headers(db_session, company)

    list_resp = client.get(f"/api/v2/studio/static-sites/{site.id}/previews", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    get_resp = client.get(f"/api/v2/studio/static-sites/{site.id}/previews/{preview_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["pr_number"] == 7


@pytest.mark.integration
def test_authenticated_endpoints_enforce_company_isolation(client, db_session, webhook_secret, company_and_site):
    from app.companies.model import Company

    company_a, site_a = company_and_site
    _connected(db_session, site_a)
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    client.post(WEBHOOK_PATH, content=body, headers=_headers(body))
    preview_id = str(_previews_for_site(db_session, site_a.id)[0].id)

    company_b = Company(id=uuid4(), slug=f"preview-iso-{uuid4().hex[:8]}", name="Company B Isolation")
    db_session.add(company_b)
    db_session.commit()
    headers_b, _user_b = _admin_headers(db_session, company_b)

    resp = client.get(f"/api/v2/studio/static-sites/{site_a.id}/previews/{preview_id}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.integration
def test_manual_close_enqueues_async_teardown(client, db_session, webhook_secret, company_and_site, redis_client):
    company, site = company_and_site
    _connected(db_session, site)
    body = _pr_body(repository_id=555, owner="octocat", name="app", installation_id=999)
    client.post(WEBHOOK_PATH, content=body, headers=_headers(body))
    preview_id = str(_previews_for_site(db_session, site.id)[0].id)

    headers, _user = _admin_headers(db_session, company)
    redis_client.delete("thtwaat:jobs")

    resp = client.delete(f"/api/v2/studio/static-sites/{site.id}/previews/{preview_id}", headers=headers)

    assert resp.status_code == 202
    raw = redis_client.rpop("thtwaat:jobs")
    assert raw is not None
    job = json.loads(raw)
    assert job["type"] == "static_site.preview_teardown"
    assert job["reason"] == "manual"
    # Async, per spec — the row itself is NOT synchronously torn down yet.
    db_session.expire_all()
    row = _previews_for_site(db_session, site.id)[0]
    assert row.status != "torn_down"
