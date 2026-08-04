"""Super Admin RBAC unit coverage (Module A) — stdlib + app.rbac only."""
from __future__ import annotations

from app.rbac.enums import EnterpriseRole, Permission
from app.rbac.policy import ROLE_PERMISSIONS


def test_super_admin_role_and_platform_permission():
    assert EnterpriseRole.SUPER_ADMIN.value == "super_admin"
    assert Permission.PLATFORM_ADMIN in ROLE_PERMISSIONS[EnterpriseRole.SUPER_ADMIN]


def test_company_owner_is_not_platform_admin_by_default():
    perms = ROLE_PERMISSIONS[EnterpriseRole.COMPANY_OWNER]
    assert Permission.PLATFORM_ADMIN not in perms


def test_admin_console_required_permission_string():
    assert Permission.PLATFORM_ADMIN.value == "platform:admin"
