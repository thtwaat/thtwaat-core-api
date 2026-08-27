"""Regression tests for the Studio deployment SSE stream's authentication.

Bug: GET /api/v2/studio/projects/{project_id}/deployments/{deployment_id}/stream
used the same header-only Depends(get_current_user) as every other Studio
endpoint. The browser's native EventSource API cannot set request headers,
so the frontend (apps/templates/saas/src/app/app/studio/page.tsx) has always
passed the access token as a `?access_token=` query parameter instead —
which the header-only dependency never looked at, so every real stream
connection 401'd even for an otherwise fully authenticated session (the
deployments list, launch-diagnostics, and launch-checklist endpoints all
worked fine with the exact same token, since those ARE called with a normal
Authorization header via fetch()).

Fix: app/studio/router.py::get_current_user_for_stream — used ONLY on this
one route — checks the Authorization header first (so any non-browser
caller that can set headers keeps working unchanged) and falls back to the
`access_token` query parameter only when no header is present, then
validates through the exact same AuthService.get_current_user_profile() as
every other authenticated request. No other endpoint's auth dependency was
touched.

Requires: docker compose -f docker-compose.test.yml up -d db redis
(auto-skipped otherwise via the `integration_stack` fixture).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

STREAM_PATH_TEMPLATE = "/api/v2/studio/projects/{project_id}/deployments/{deployment_id}/stream"


def _make_company_and_user(db_session):
    from app.companies.model import Company
    from app.rbac.enums import EnterpriseRole
    from app.users.model import User, UserStatus

    company = Company(id=uuid4(), slug=f"stream-auth-{uuid4().hex[:8]}", name="Stream Auth Co")
    db_session.add(company)
    db_session.commit()

    user = User(
        id=uuid4(), company_id=company.id, email=f"user-{uuid4().hex[:8]}@example.com",
        hashed_password="x", first_name="Test", last_name="User",
        role=EnterpriseRole.ADMIN, status=UserStatus.ACTIVE, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return company, user


def _make_project(db_session, company):
    from app.studio.models import StudioProject

    project = StudioProject(
        id=uuid4(), workspace_id=company.id, title="Stream Auth Project", prompt="A test project", status="draft",
    )
    db_session.add(project)
    db_session.commit()
    return project


def _stream_url(project_id, deployment_id):
    return STREAM_PATH_TEMPLATE.format(project_id=project_id, deployment_id=deployment_id)


@pytest.mark.integration
def test_stream_accepts_access_token_query_param_like_the_browsers_eventsource_does(client, db_session):
    """The exact regression: a real, valid access token passed ONLY as
    `?access_token=` (no Authorization header at all — matching what
    EventSource actually sends) must authenticate successfully. Success
    here means the request gets PAST auth and into the service layer — a
    404 for the (nonexistent) deployment proves exactly that boundary,
    without needing to stand up a real running deployment/build pipeline."""
    from app.auth.service import AuthService

    company, user = _make_company_and_user(db_session)
    project = _make_project(db_session, company)
    token = AuthService(db_session).create_access_token(str(user.id))

    url = f"{_stream_url(project.id, uuid4())}?access_token={token}"
    resp = client.get(url)  # deliberately NO Authorization header

    assert resp.status_code == 404
    assert resp.json()["error"] == "Deployment not found"


@pytest.mark.integration
def test_stream_still_accepts_authorization_header_for_non_browser_callers(client, db_session):
    """Non-EventSource callers (curl, a future server-to-server caller) that
    CAN set headers must keep working exactly as before — the query-param
    fallback must be additive, never a replacement for header auth."""
    from app.auth.service import AuthService

    company, user = _make_company_and_user(db_session)
    project = _make_project(db_session, company)
    token = AuthService(db_session).create_access_token(str(user.id))

    resp = client.get(
        _stream_url(project.id, uuid4()), headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 404
    assert resp.json()["error"] == "Deployment not found"


@pytest.mark.integration
def test_stream_with_no_token_anywhere_is_401(client, db_session):
    """No Authorization header AND no access_token query param must still
    401 — the fallback must not accidentally make the endpoint unauthenticated."""
    company, user = _make_company_and_user(db_session)
    project = _make_project(db_session, company)

    resp = client.get(_stream_url(project.id, uuid4()))

    assert resp.status_code == 401


@pytest.mark.integration
def test_stream_with_invalid_access_token_query_param_is_401(client, db_session):
    """A garbage/expired access_token in the query string must be rejected
    through the SAME AuthService validation as a bad Authorization header —
    never silently treated as authenticated."""
    company, user = _make_company_and_user(db_session)
    project = _make_project(db_session, company)

    resp = client.get(f"{_stream_url(project.id, uuid4())}?access_token=not-a-real-jwt")

    assert resp.status_code == 401


@pytest.mark.integration
def test_stream_query_param_cannot_bypass_company_isolation(client, db_session):
    """A valid access_token for Company A's user, passed as a query param,
    must not be able to reach Company B's project — the fallback must not
    weaken tenant isolation just because it reads the token from a
    different place."""
    from app.auth.service import AuthService

    company_a, user_a = _make_company_and_user(db_session)
    company_b, _user_b = _make_company_and_user(db_session)
    project_b = _make_project(db_session, company_b)
    token_a = AuthService(db_session).create_access_token(str(user_a.id))

    url = f"{_stream_url(project_b.id, uuid4())}?access_token={token_a}"
    resp = client.get(url)

    assert resp.status_code == 404  # "not found", never leaks that it belongs to another company
    assert resp.json()["error"] == "Studio project not found"
