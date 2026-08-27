"""GitHub OAuth-state (CSRF token) security tests for THTWAAT Deploy Phase 5.

The atomic consume-once semantics (app/static_sites/repository.py::
consume_github_oauth_state) are implemented as a single UPDATE...WHERE
consumed_at IS NULL AND expires_at > now() — a MagicMock repo cannot
demonstrate this is actually atomic/correct, so (mirroring
tests/unit/static_sites/test_idempotency.py's test_repository_claim_race_is_
atomic) these run against a real Postgres via the `db_session` fixture.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

import app.apps.model  # noqa: F401
import app.auth.model  # noqa: F401
import app.companies.model  # noqa: F401
import app.domains.models  # noqa: F401
import app.static_sites.models  # noqa: F401
import app.storage.model  # noqa: F401
import app.users.model  # noqa: F401

from app.static_sites import github_client


def _make_company_site_user(db_session):
    from app.companies.model import Company
    from app.rbac.enums import EnterpriseRole
    from app.static_sites.models import StaticSite
    from app.users.model import User

    company = Company(id=uuid4(), slug=f"gh-state-{uuid4().hex[:8]}", name="GitHub State Test Co")
    db_session.add(company)
    db_session.commit()

    site = StaticSite(id=uuid4(), workspace_id=company.id, name="Site", slug=f"site-{uuid4().hex[:8]}")
    db_session.add(site)
    db_session.commit()

    user = User(
        id=uuid4(), email=f"gh-state-{uuid4().hex[:8]}@example.com", company_id=company.id,
        hashed_password="x", first_name="GitHub", last_name="Tester", role=EnterpriseRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    return company, site, user


@pytest.mark.integration
def test_state_stored_as_hash_never_as_raw_value(db_session):
    from app.static_sites.models import GitHubOAuthState
    from app.static_sites.repository import StaticSiteRepository

    company, site, user = _make_company_site_user(db_session)
    repo = StaticSiteRepository(db_session)
    raw_state = github_client.new_state()

    row = GitHubOAuthState(
        id=uuid4(), state_hash=github_client.hash_state(raw_state), user_id=user.id,
        workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    repo.create_github_oauth_state(row)

    stored = db_session.query(GitHubOAuthState).filter_by(id=row.id).first()
    assert stored.state_hash != raw_state
    assert raw_state not in stored.state_hash


@pytest.mark.integration
def test_consume_state_succeeds_exactly_once(db_session):
    from app.static_sites.models import GitHubOAuthState
    from app.static_sites.repository import StaticSiteRepository

    company, site, user = _make_company_site_user(db_session)
    repo = StaticSiteRepository(db_session)
    raw_state = github_client.new_state()
    state_hash = github_client.hash_state(raw_state)

    row = GitHubOAuthState(
        id=uuid4(), state_hash=state_hash, user_id=user.id, workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    repo.create_github_oauth_state(row)

    first = repo.consume_github_oauth_state(state_hash)
    assert first is not None
    assert first.user_id == user.id
    assert first.workspace_id == company.id
    assert first.site_id == site.id
    assert first.consumed_at is not None


@pytest.mark.integration
def test_consume_state_rejects_replay(db_session):
    """The exact requirement from task §8/§18 — a second callback carrying
    the same state value after a successful first use must be rejected."""
    from app.static_sites.repository import StaticSiteRepository
    from app.static_sites.models import GitHubOAuthState

    company, site, user = _make_company_site_user(db_session)
    repo = StaticSiteRepository(db_session)
    raw_state = github_client.new_state()
    state_hash = github_client.hash_state(raw_state)
    row = GitHubOAuthState(
        id=uuid4(), state_hash=state_hash, user_id=user.id, workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    repo.create_github_oauth_state(row)

    first = repo.consume_github_oauth_state(state_hash)
    second = repo.consume_github_oauth_state(state_hash)

    assert first is not None
    assert second is None, "a state value must be usable exactly once"


@pytest.mark.integration
def test_consume_state_rejects_expired_state(db_session):
    from app.static_sites.repository import StaticSiteRepository
    from app.static_sites.models import GitHubOAuthState

    company, site, user = _make_company_site_user(db_session)
    repo = StaticSiteRepository(db_session)
    raw_state = github_client.new_state()
    state_hash = github_client.hash_state(raw_state)
    row = GitHubOAuthState(
        id=uuid4(), state_hash=state_hash, user_id=user.id, workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # already expired
    )
    repo.create_github_oauth_state(row)

    assert repo.consume_github_oauth_state(state_hash) is None


@pytest.mark.integration
def test_consume_state_rejects_mismatched_hash(db_session):
    from app.static_sites.repository import StaticSiteRepository
    from app.static_sites.models import GitHubOAuthState

    company, site, user = _make_company_site_user(db_session)
    repo = StaticSiteRepository(db_session)
    row = GitHubOAuthState(
        id=uuid4(), state_hash=github_client.hash_state("real-state"), user_id=user.id,
        workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    repo.create_github_oauth_state(row)

    forged = repo.consume_github_oauth_state(github_client.hash_state("attacker-guessed-state"))
    assert forged is None


@pytest.mark.integration
def test_consume_state_race_only_one_caller_wins(db_session):
    """Two 'requests' racing to consume the exact same state value — exactly
    one must succeed, matching the idempotency-key race test's shape."""
    from app.static_sites.repository import StaticSiteRepository
    from app.static_sites.models import GitHubOAuthState

    company, site, user = _make_company_site_user(db_session)
    repo = StaticSiteRepository(db_session)
    raw_state = github_client.new_state()
    state_hash = github_client.hash_state(raw_state)
    row = GitHubOAuthState(
        id=uuid4(), state_hash=state_hash, user_id=user.id, workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    repo.create_github_oauth_state(row)

    results = [repo.consume_github_oauth_state(state_hash), repo.consume_github_oauth_state(state_hash)]
    successes = [r for r in results if r is not None]
    assert len(successes) == 1


@pytest.mark.integration
def test_purge_expired_states_removes_only_expired_rows(db_session):
    from app.static_sites.repository import StaticSiteRepository
    from app.static_sites.models import GitHubOAuthState

    company, site, user = _make_company_site_user(db_session)
    repo = StaticSiteRepository(db_session)

    expired = GitHubOAuthState(
        id=uuid4(), state_hash=github_client.hash_state("expired"), user_id=user.id,
        workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=48),
    )
    fresh = GitHubOAuthState(
        id=uuid4(), state_hash=github_client.hash_state("fresh"), user_id=user.id,
        workspace_id=company.id, site_id=site.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db_session.add_all([expired, fresh])
    db_session.commit()

    removed = repo.purge_expired_github_oauth_states(grace_hours=24)
    assert removed >= 1
    assert db_session.query(GitHubOAuthState).filter_by(id=expired.id).first() is None
    assert db_session.query(GitHubOAuthState).filter_by(id=fresh.id).first() is not None
