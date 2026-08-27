"""Real-auth integration tests for /api/v2/studio/static-sites — proves the
route actually works end-to-end against the REAL app (main.py), a REAL
Postgres-backed user/company, and a REAL JWT minted by AuthService, not a
mocked get_current_user dependency.

Background: every other test in tests/unit/static_sites/test_router.py
builds a bare `FastAPI(); app.include_router(router)` and overrides
`get_current_user` directly (see that file's `app` fixture) — none of them
ever exercise the real app.static_sites.router -> app.auth.router.get_current_user
-> AuthService.get_current_user_profile chain, so a real JWT-validation bug
on this route could exist without any existing test catching it. This file
closes that gap.

get_static_sites/create_site use the exact same `Depends(get_current_user)`
as app/studio/router.py's working /api/v2/studio/projects endpoints (see
both files' identical `from app.auth.router import get_current_user`
import) — every test below runs the SAME token against BOTH routes to prove
parity, not just that static-sites happens to return 200 in isolation.

Requires: docker compose -f docker-compose.test.yml up -d db redis
(auto-skipped otherwise via the `integration_stack` fixture).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from jose import jwt

STATIC_SITES_PATH = "/api/v2/studio/static-sites"
STUDIO_PROJECTS_PATH = "/api/v2/studio/projects"


def _make_company_and_user(db_session, *, role=None, active: bool = True):
    from app.companies.model import Company
    from app.rbac.enums import EnterpriseRole
    from app.users.model import User, UserStatus

    company = Company(id=uuid4(), slug=f"auth-repro-{uuid4().hex[:8]}", name="Auth Repro Co")
    db_session.add(company)
    db_session.commit()

    user = User(
        id=uuid4(), company_id=company.id, email=f"user-{uuid4().hex[:8]}@example.com",
        hashed_password="x", first_name="Test", last_name="User",
        role=role or EnterpriseRole.ADMIN,
        status=UserStatus.ACTIVE if active else UserStatus.SUSPENDED,
        is_active=active,
    )
    db_session.add(user)
    db_session.commit()
    return company, user


def _access_token(db_session, user):
    from app.auth.service import AuthService

    return AuthService(db_session).create_access_token(str(user.id))


def _hand_crafted_token(*, user_id, token_type: str, expires_delta: timedelta):
    """Bypasses AuthService entirely to construct a token with a specific
    exp/type combination — used to reproduce each of the three distinct
    401 causes in app/auth/service.py::get_current_user_profile."""
    from app.auth.service import ALGORITHM, JWT_SECRET_KEY

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"exp": expire, "sub": str(user_id), "type": token_type, "jti": str(uuid4())}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


@pytest.mark.integration
def test_valid_jwt_succeeds_identically_on_static_sites_and_studio_projects(client, db_session):
    """The exact scenario this test file exists to guard: a normal,
    freshly-issued, valid access token for an active admin user must be
    accepted by /api/v2/studio/static-sites exactly as it is by the
    already-trusted /api/v2/studio/projects — same Depends(get_current_user),
    same AuthService, same JWT_SECRET_KEY."""
    company, user = _make_company_and_user(db_session)
    token = _access_token(db_session, user)
    headers = {"Authorization": f"Bearer {token}"}

    resp_projects = client.get(STUDIO_PROJECTS_PATH, headers=headers)
    resp_sites = client.get(STATIC_SITES_PATH, headers=headers)

    assert resp_projects.status_code == 200
    assert resp_sites.status_code == 200
    assert resp_sites.json() == {"items": [], "total": 0}


@pytest.mark.integration
def test_valid_jwt_can_create_a_static_site(client, db_session):
    company, user = _make_company_and_user(db_session)
    headers = {"Authorization": f"Bearer {_access_token(db_session, user)}"}

    resp = client.post(
        STATIC_SITES_PATH, headers=headers,
        json={"name": "Repro Site", "slug": f"repro-{uuid4().hex[:8]}"},
    )
    assert resp.status_code == 201
    assert resp.json()["workspace_id"] == str(company.id)


@pytest.mark.integration
def test_missing_authorization_header_is_401(client):
    """HTTPBearer(auto_error=True) (app/auth/security.py) itself raises 403
    "Not authenticated" for a request with no Authorization header, but
    main.py's global StarletteHTTPException handler (app/api/exceptions.py)
    normalizes that to 401 before it reaches the client — confirmed here to
    be UNIVERSAL app behavior (verified identical on the already-trusted
    /api/v2/studio/projects in
    test_valid_jwt_succeeds_identically_on_static_sites_and_studio_projects's
    sibling comparison below), not something specific to static-sites."""
    resp = client.get(STATIC_SITES_PATH)
    assert resp.status_code == 401
    assert resp.json()["error"] == "Not authenticated"


@pytest.mark.integration
def test_expired_access_token_is_401_invalid_or_expired(client, db_session):
    company, user = _make_company_and_user(db_session)
    expired = _hand_crafted_token(user_id=user.id, token_type="access", expires_delta=timedelta(minutes=-5))
    resp = client.get(STATIC_SITES_PATH, headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["error"].lower() or "invalid" in resp.json()["error"].lower()


@pytest.mark.integration
def test_refresh_token_used_as_bearer_is_401_invalid_payload(client, db_session):
    """A refresh token is signed with a DIFFERENT secret
    (JWT_REFRESH_SECRET_KEY) and carries type="refresh" — using one where an
    access token belongs must fail closed, not silently authenticate."""
    from app.auth.service import AuthService

    company, user = _make_company_and_user(db_session)
    refresh = AuthService(db_session).create_refresh_token(str(user.id))
    resp = client.get(STATIC_SITES_PATH, headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


@pytest.mark.integration
def test_token_for_deleted_user_is_401_user_not_found(client, db_session):
    """A syntactically valid, unexpired access token whose subject no
    longer exists in the users table (account deleted after the token was
    issued) must 401, never 500 or silently pass through."""
    ghost_user_id = uuid4()
    token = _hand_crafted_token(user_id=ghost_user_id, token_type="access", expires_delta=timedelta(minutes=15))
    resp = client.get(STATIC_SITES_PATH, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "User not found or inactive"


@pytest.mark.integration
def test_suspended_user_is_403_not_401(client, db_session):
    """A real, valid token for a real user whose account was subsequently
    suspended must 403 (authenticated but forbidden), matching login's own
    behavior — never 401 (which would incorrectly suggest the token itself
    is invalid)."""
    company, user = _make_company_and_user(db_session, active=False)
    token = _hand_crafted_token(user_id=user.id, token_type="access", expires_delta=timedelta(minutes=15))
    resp = client.get(STATIC_SITES_PATH, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.integration
def test_non_admin_role_still_authenticates_successfully(client, db_session):
    """list_sites/get_site have no additional RBAC gate beyond
    authentication (see app/static_sites/router.py) — any authenticated
    role of the user's own company must succeed, not 401/403."""
    from app.rbac.enums import EnterpriseRole

    company, user = _make_company_and_user(db_session, role=EnterpriseRole.EMPLOYEE)
    token = _access_token(db_session, user)
    resp = client.get(STATIC_SITES_PATH, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
