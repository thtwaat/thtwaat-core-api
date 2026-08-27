"""Phase 6C-1 — RBAC coverage for Permission.CODING_AGENT_ACCESS.

Pure enum/policy tests — no database, no HTTP client. Mirrors
RequirePermission's own real call shape (app.command_center.router's
require_platform_admin): RequirePermission(permission)(role_string).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.rbac.dependencies import RequirePermission
from app.rbac.enums import EnterpriseRole, Permission


@pytest.mark.unit
@pytest.mark.parametrize(
    "role",
    [
        EnterpriseRole.SUPER_ADMIN,
        EnterpriseRole.COMPANY_OWNER,
        EnterpriseRole.ADMIN,
        EnterpriseRole.MANAGER,
        EnterpriseRole.DEVELOPER,
        EnterpriseRole.EMPLOYEE,
    ],
)
def test_roles_with_coding_agent_access(role):
    # Must not raise.
    RequirePermission(Permission.CODING_AGENT_ACCESS)(role.value)


@pytest.mark.unit
def test_viewer_denied_coding_agent_access():
    with pytest.raises(HTTPException) as exc_info:
        RequirePermission(Permission.CODING_AGENT_ACCESS)(EnterpriseRole.VIEWER.value)
    assert exc_info.value.status_code == 403


@pytest.mark.unit
def test_unrecognized_role_denied_coding_agent_access():
    with pytest.raises(HTTPException) as exc_info:
        RequirePermission(Permission.CODING_AGENT_ACCESS)("not-a-real-role")
    assert exc_info.value.status_code == 403
