"""Unit tests for public signup role policy (P0 privilege escalation fix)."""

import pytest
from fastapi import HTTPException

from app.rbac.enums import EnterpriseRole
from app.users.signup_roles import PUBLIC_SIGNUP_ROLES, assert_create_role_allowed


@pytest.mark.unit
def test_public_allowlist_is_only_owner_and_employee():
    assert PUBLIC_SIGNUP_ROLES == {
        EnterpriseRole.COMPANY_OWNER,
        EnterpriseRole.EMPLOYEE,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "role",
    [EnterpriseRole.COMPANY_OWNER, EnterpriseRole.EMPLOYEE],
)
def test_public_signup_allows_safe_roles(role):
    assert_create_role_allowed(role, allow_privileged=False)


@pytest.mark.unit
@pytest.mark.parametrize(
    "role",
    [
        EnterpriseRole.SUPER_ADMIN,
        EnterpriseRole.ADMIN,
        EnterpriseRole.MANAGER,
        EnterpriseRole.DEVELOPER,
        EnterpriseRole.VIEWER,
    ],
)
def test_public_signup_rejects_privileged_roles(role):
    with pytest.raises(HTTPException) as exc:
        assert_create_role_allowed(role, allow_privileged=False)
    assert exc.value.status_code == 403


@pytest.mark.unit
def test_platform_admin_may_assign_any_role():
    for role in EnterpriseRole:
        assert_create_role_allowed(role, allow_privileged=True)
