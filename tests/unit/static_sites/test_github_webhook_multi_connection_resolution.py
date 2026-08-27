"""Regression tests for the P0 cross-tenant GitHub webhook/preview
resolution fix (repository.py::list_github_connections_by_repository +
github_webhook_router.py's fan-out over _handle_push/_handle_pull_request).

Background (see the investigation this fix came out of): GitHubConnection
has NO unique constraint on (repository_id, installation_id) — only on
site_id (uq_github_connections_site, app/static_sites/models.py). Tracing
the full connect/select_repository/disconnect lifecycle
(app/static_sites/github_service.py) confirmed two legitimate business
scenarios where more than one GitHubConnection row genuinely matches the
same (repository_id, installation_id):

  1. One company connects the SAME repo to two different sites (e.g. a
     staging site and a production site built from one repo).
  2. Two DIFFERENT companies each hold their own connection against the
     SAME installation_id — this happens whenever the installing GitHub
     account/org grants the app access on behalf of more than one THTWAAT
     company (an agency's installation used for several clients, or two
     THTWAAT companies run by collaborators on the same GitHub org):
     GitHub hands back the identical installation_id to every
     /github/callback for that account, and select_repository() never
     checks whether a repository_id is already selected elsewhere before
     saving the connection.

Because scenario 1 is ordinary, intended usage, a database-level unique
constraint on (repository_id, installation_id) would be WRONG — it would
break a company's ability to run two sites off one repo. The actual bug was
in the resolution query: get_github_connection_by_repository() used
`.first()` with no ORDER BY, silently picking an arbitrary one of the
matching rows. That could (a) drop a legitimate second site's
deployment/preview entirely on some pushes, and (b) in scenario 2, route a
webhook to the WRONG company's site outright.

The fix replaces single-row resolution with
list_github_connections_by_repository() (returns every matching row,
deterministically ordered) and makes both webhook handlers fan out over
every row whose selected_branch/base branch actually matches the event —
so every legitimately-connected site gets its own independent, correct
outcome, and no site is ever selected on another site's behalf.

Every test below mints its own fresh, random repository_id/installation_id
(never a literal shared with any other test in this suite) specifically so
these tests remain correct in isolation regardless of what else has run
against the same real Postgres test database in the same session (db_session
commits are never rolled back between tests — see tests/conftest.py).

Requires: docker compose -f docker-compose.test.yml up -d db redis
(auto-skipped otherwise via the `integration_stack` fixture).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import random
from uuid import uuid4

import pytest

WEBHOOK_PATH = "/api/v2/studio/static-sites/github/webhook"
TEST_SECRET = "integration-test-webhook-secret-value"
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


def _sign(body: bytes, secret: str = TEST_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _push_body(*, repository_id: int, installation_id: int, branch: str = "main",
                commit_sha: str = COMMIT_A, owner: str = "octocat", name: str = "app") -> bytes:
    payload = {
        "ref": f"refs/heads/{branch}",
        "after": commit_sha,
        "deleted": False,
        "repository": {"id": repository_id, "name": name, "owner": {"login": owner}},
        "installation": {"id": installation_id},
        "sender": {"login": owner},
    }
    return json.dumps(payload).encode("utf-8")


def _pr_body(*, repository_id: int, installation_id: int, pr_number: int, action: str = "opened",
             head_sha: str = COMMIT_A, head_ref: str = "feature-x", base_ref: str = "main",
             owner: str = "octocat", name: str = "app") -> bytes:
    payload = {
        "action": action,
        "number": pr_number,
        "repository": {"id": repository_id, "name": name, "owner": {"login": owner}},
        "installation": {"id": installation_id},
        "pull_request": {
            "number": pr_number,
            "head": {"sha": head_sha, "ref": head_ref, "repo": {"id": repository_id}},
            "base": {"ref": base_ref, "repo": {"id": repository_id}},
        },
        "sender": {"login": owner},
    }
    return json.dumps(payload).encode("utf-8")


def _headers(body: bytes, *, event: str, secret: str = TEST_SECRET) -> dict:
    return {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": str(uuid4()),
        "X-Hub-Signature-256": _sign(body, secret=secret),
        "Content-Type": "application/json",
    }


@pytest.fixture
def webhook_secret(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "GITHUB_APP_WEBHOOK_SECRET", TEST_SECRET)
    return TEST_SECRET


@pytest.fixture
def fresh_repo_ids():
    """A (repository_id, installation_id) pair guaranteed not to collide
    with any literal used elsewhere in this test suite — every test in this
    file calls this fixture independently, so two tests in the SAME file
    never collide with each other either."""
    return random.randint(10_000_000, 99_999_999), random.randint(1_000_000, 9_999_999)


def _make_company_and_site(db_session, *, slug_prefix: str) -> tuple:
    from app.companies.model import Company
    from app.static_sites.models import StaticSite

    company = Company(id=uuid4(), slug=f"{slug_prefix}-{uuid4().hex[:8]}", name=f"{slug_prefix} Co")
    db_session.add(company)
    db_session.commit()

    site = StaticSite(id=uuid4(), workspace_id=company.id, name="Site", slug=f"site-{uuid4().hex[:8]}")
    db_session.add(site)
    db_session.commit()
    return company, site


def _connect(db_session, site, *, repository_id: int, installation_id: int, branch: str = "main"):
    from app.static_sites.models import GitHubConnection

    conn = GitHubConnection(
        id=uuid4(), workspace_id=site.workspace_id, site_id=site.id,
        installation_id=str(installation_id), github_account_id="1", github_username="octocat",
        account_type="Organization", repository_owner="octocat", repository_name="app",
        repository_id=str(repository_id), default_branch="main", selected_branch=branch,
    )
    db_session.add(conn)
    db_session.commit()
    return conn


def _deployments_for_site(db_session, site_id):
    from app.static_sites.models import StaticSiteDeployment

    return (
        db_session.query(StaticSiteDeployment)
        .filter(StaticSiteDeployment.site_id == site_id)
        .all()
    )


def _previews_for_site(db_session, site_id):
    from app.static_sites.models import StaticSitePreviewDeployment

    return (
        db_session.query(StaticSitePreviewDeployment)
        .filter(StaticSitePreviewDeployment.site_id == site_id)
        .all()
    )


# ---- scenario 1: same company, two sites, same repo — different branches ----


@pytest.mark.integration
def test_two_sites_same_repo_different_branches_push_never_cross_deploys(
    client, db_session, webhook_secret, fresh_repo_ids
):
    """One company runs a 'staging' site tracking `develop` and a
    'production' site tracking `main`, both off the exact same GitHub repo.
    A push to `main` must deploy ONLY the production site — the old
    .first()-based resolution could non-deterministically pick either
    connection regardless of which branch was actually pushed, since the
    branch check only ran AFTER a single row had already been chosen."""
    repository_id, installation_id = fresh_repo_ids
    company, prod_site = _make_company_and_site(db_session, slug_prefix="multisite")
    from app.static_sites.models import StaticSite

    staging_site = StaticSite(
        id=uuid4(), workspace_id=company.id, name="Staging", slug=f"staging-{uuid4().hex[:8]}"
    )
    db_session.add(staging_site)
    db_session.commit()

    _connect(db_session, prod_site, repository_id=repository_id, installation_id=installation_id, branch="main")
    _connect(db_session, staging_site, repository_id=repository_id, installation_id=installation_id, branch="develop")

    body = _push_body(repository_id=repository_id, installation_id=installation_id, branch="main", commit_sha=COMMIT_A)
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, event="push"))

    assert resp.status_code == 202
    data = resp.json()
    assert "deployment_ids" not in data  # exactly one site matched — no fan-out noise in the common case

    prod_rows = _deployments_for_site(db_session, prod_site.id)
    staging_rows = _deployments_for_site(db_session, staging_site.id)
    assert len(prod_rows) == 1
    assert prod_rows[0].github_branch == "main"
    assert staging_rows == []  # the staging site (tracking `develop`) must never see this push


@pytest.mark.integration
def test_two_sites_same_repo_same_branch_push_fans_out_to_both(client, db_session, webhook_secret, fresh_repo_ids):
    """The legitimate multi-site case: two sites of the SAME company both
    intentionally track `main` of the same repo (e.g. mirrored deploys to
    two domains). A single push must deploy BOTH — under the old .first()
    resolution, one of these two sites would silently never be deployed."""
    repository_id, installation_id = fresh_repo_ids
    company, site_a = _make_company_and_site(db_session, slug_prefix="mirror")
    from app.static_sites.models import StaticSite

    site_b = StaticSite(id=uuid4(), workspace_id=company.id, name="Mirror B", slug=f"mirror-b-{uuid4().hex[:8]}")
    db_session.add(site_b)
    db_session.commit()

    _connect(db_session, site_a, repository_id=repository_id, installation_id=installation_id, branch="main")
    _connect(db_session, site_b, repository_id=repository_id, installation_id=installation_id, branch="main")

    body = _push_body(repository_id=repository_id, installation_id=installation_id, branch="main", commit_sha=COMMIT_A)
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, event="push"))

    assert resp.status_code == 202
    data = resp.json()
    # The wire response deliberately never lists every fanned-out id (see
    # _handle_push's rationale — a shared installation can fan out across
    # different tenants, and the response body must never bundle another
    # tenant's identifiers). DB state is the authoritative check that BOTH
    # sites actually got deployed, not just whichever id the response names.
    assert "deployment_ids" not in data

    rows_a = _deployments_for_site(db_session, site_a.id)
    rows_b = _deployments_for_site(db_session, site_b.id)
    assert len(rows_a) == 1 and rows_a[0].github_commit_sha == COMMIT_A
    assert len(rows_b) == 1 and rows_b[0].github_commit_sha == COMMIT_A


# ---- scenario 2: two different companies sharing one installation_id -------


@pytest.mark.integration
def test_shared_installation_different_companies_different_branches_no_cross_tenant_deploy(
    client, db_session, webhook_secret, fresh_repo_ids
):
    """Simulates an agency-style shared GitHub App installation: two
    DIFFERENT companies each hold their own GitHubConnection against the
    identical (repository_id, installation_id) — nothing in the schema
    prevents this (no unique constraint beyond site_id). Company A tracks
    `main`, Company B tracks `release`. A push to `main` must deploy ONLY
    Company A's site — Company B must never see a deployment, a preview, or
    any row at all for a push it has no business receiving. This is the
    direct regression test for the P0 finding: the old `.first()` query
    could resolve this push to Company B's connection instead, misrouting a
    tenant's push to a stranger's site."""
    repository_id, installation_id = fresh_repo_ids
    company_a, site_a = _make_company_and_site(db_session, slug_prefix="tenant-a")
    company_b, site_b = _make_company_and_site(db_session, slug_prefix="tenant-b")
    assert company_a.id != company_b.id

    _connect(db_session, site_a, repository_id=repository_id, installation_id=installation_id, branch="main")
    _connect(db_session, site_b, repository_id=repository_id, installation_id=installation_id, branch="release")

    body = _push_body(repository_id=repository_id, installation_id=installation_id, branch="main", commit_sha=COMMIT_A)
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, event="push"))

    assert resp.status_code == 202
    data = resp.json()
    assert "deployment_ids" not in data

    rows_a = _deployments_for_site(db_session, site_a.id)
    rows_b = _deployments_for_site(db_session, site_b.id)
    assert len(rows_a) == 1
    assert str(rows_a[0].id) == data["deployment_id"]
    assert rows_b == [], "Company B must never receive a deployment for Company A's push"


@pytest.mark.integration
def test_shared_installation_different_companies_pull_request_no_cross_tenant_preview(
    client, db_session, webhook_secret, fresh_repo_ids
):
    """Same shared-installation scenario as above, for the pull_request /
    Preview Deployments path: Company A and Company B share
    (repository_id, installation_id) but track different base branches. A
    PR opened against Company A's tracked branch must create a preview
    under Company A's site only — never under Company B's."""
    repository_id, installation_id = fresh_repo_ids
    company_a, site_a = _make_company_and_site(db_session, slug_prefix="pr-tenant-a")
    company_b, site_b = _make_company_and_site(db_session, slug_prefix="pr-tenant-b")

    _connect(db_session, site_a, repository_id=repository_id, installation_id=installation_id, branch="main")
    _connect(db_session, site_b, repository_id=repository_id, installation_id=installation_id, branch="release")

    body = _pr_body(
        repository_id=repository_id, installation_id=installation_id, pr_number=101,
        action="opened", base_ref="main",
    )
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, event="pull_request"))

    assert resp.status_code == 202
    data = resp.json()
    assert "preview_ids" not in data

    previews_a = _previews_for_site(db_session, site_a.id)
    previews_b = _previews_for_site(db_session, site_b.id)
    assert len(previews_a) == 1
    assert str(previews_a[0].id) == data["preview_id"]
    assert previews_b == [], "Company B must never receive a preview for Company A's pull request"


@pytest.mark.integration
def test_shared_installation_same_branch_pull_request_fans_out_to_both_tenants(
    client, db_session, webhook_secret, fresh_repo_ids
):
    """If two companies sharing an installation both happen to track the
    SAME branch of the same repo, a matching PR legitimately creates a
    preview for each of them independently — this is not a leak (each
    company only ever sees its OWN site/preview row; no data crosses
    between them), just confirmation that fan-out doesn't accidentally
    drop one of two equally-valid matches."""
    repository_id, installation_id = fresh_repo_ids
    company_a, site_a = _make_company_and_site(db_session, slug_prefix="shared-a")
    company_b, site_b = _make_company_and_site(db_session, slug_prefix="shared-b")

    _connect(db_session, site_a, repository_id=repository_id, installation_id=installation_id, branch="main")
    _connect(db_session, site_b, repository_id=repository_id, installation_id=installation_id, branch="main")

    body = _pr_body(
        repository_id=repository_id, installation_id=installation_id, pr_number=202,
        action="opened", base_ref="main",
    )
    resp = client.post(WEBHOOK_PATH, content=body, headers=_headers(body, event="pull_request"))

    assert resp.status_code == 202
    data = resp.json()
    # The wire response deliberately never lists every fanned-out id (see
    # _handle_pull_request's rationale — bundling both tenants' preview ids
    # into one webhook ack response would leak Company B's identifier to
    # whoever can see Company A's side of a shared installation's webhook
    # deliveries). DB state is the authoritative check that BOTH companies
    # actually got their own preview.
    assert "preview_ids" not in data

    previews_a = _previews_for_site(db_session, site_a.id)
    previews_b = _previews_for_site(db_session, site_b.id)
    assert len(previews_a) == 1
    assert len(previews_b) == 1
    assert previews_a[0].id != previews_b[0].id


# ---- not-connected / no-match cases must still be indistinguishable -------


@pytest.mark.integration
def test_no_connection_at_all_and_wrong_branch_both_ignored_identically(
    client, db_session, webhook_secret, fresh_repo_ids
):
    """Guards against a regression where list_github_connections_by_repository
    returning an empty list (nothing connected) vs. a non-empty list with no
    branch match are handled differently in a way that leaks information —
    both must be a plain 200 {"ignored": true}, never a 4xx/5xx and never
    distinguishable in the response body."""
    repository_id, installation_id = fresh_repo_ids
    body_unconnected = _push_body(repository_id=repository_id, installation_id=installation_id, branch="main")
    resp_unconnected = client.post(WEBHOOK_PATH, content=body_unconnected, headers=_headers(body_unconnected, event="push"))
    assert resp_unconnected.status_code == 200
    assert resp_unconnected.json()["ignored"] is True

    company, site = _make_company_and_site(db_session, slug_prefix="branch-mismatch")
    _connect(db_session, site, repository_id=repository_id, installation_id=installation_id, branch="main")
    body_wrong_branch = _push_body(repository_id=repository_id, installation_id=installation_id, branch="feature/x")
    resp_wrong_branch = client.post(WEBHOOK_PATH, content=body_wrong_branch, headers=_headers(body_wrong_branch, event="push"))
    assert resp_wrong_branch.status_code == 200
    assert resp_wrong_branch.json()["ignored"] is True
    assert _deployments_for_site(db_session, site.id) == []
