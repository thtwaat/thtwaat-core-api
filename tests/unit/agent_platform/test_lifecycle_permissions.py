"""Unit tests for agent lifecycle helpers (no Postgres required)."""
from __future__ import annotations

from app.agent_platform.lifecycle import RETENTION_DAYS, STATUS_DELETED
from app.rbac.enums import EnterpriseRole, Permission
from app.rbac.policy import ROLE_PERMISSIONS


def test_retention_and_status_constants():
    assert RETENTION_DAYS == 30
    assert STATUS_DELETED == "DELETED"


def test_agents_delete_permission_matrix():
    assert Permission.AGENTS_DELETE in ROLE_PERMISSIONS[EnterpriseRole.SUPER_ADMIN]
    assert Permission.AGENTS_DELETE in ROLE_PERMISSIONS[EnterpriseRole.COMPANY_OWNER]
    assert Permission.AGENTS_DELETE in ROLE_PERMISSIONS[EnterpriseRole.ADMIN]
    assert Permission.AGENTS_DELETE not in ROLE_PERMISSIONS[EnterpriseRole.DEVELOPER]
    assert Permission.AGENTS_DELETE not in ROLE_PERMISSIONS[EnterpriseRole.EMPLOYEE]
    assert Permission.AGENTS_DELETE not in ROLE_PERMISSIONS[EnterpriseRole.MANAGER]
    assert Permission.AGENTS_DELETE not in ROLE_PERMISSIONS[EnterpriseRole.VIEWER]
