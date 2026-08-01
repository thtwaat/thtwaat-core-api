"""Tenant isolation helpers for authenticated company-scoped APIs."""

from __future__ import annotations

import uuid
from typing import Optional, Union

from fastapi import HTTPException
from fastapi import status as http_status

from app.auth.schema import UserProfileResponse
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import EnterpriseRole, Permission

# Roles that may manage other users inside their own company.
_COMPANY_USER_MANAGERS = frozenset(
    {
        EnterpriseRole.COMPANY_OWNER,
        EnterpriseRole.ADMIN,
    }
)


def is_platform_admin(user: Optional[UserProfileResponse]) -> bool:
    if user is None:
        return False
    try:
        RequirePermission(Permission.PLATFORM_ADMIN)(str(user.role))
        return True
    except HTTPException:
        return False


def _as_uuid(value: Union[uuid.UUID, str]) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def assert_same_company(
    actor: UserProfileResponse,
    resource_company_id: Union[uuid.UUID, str],
    *,
    not_found_detail: str = "Not found.",
) -> None:
    """Platform admins bypass; otherwise require matching company_id (404 on mismatch)."""
    if is_platform_admin(actor):
        return
    if _as_uuid(actor.company_id) != _as_uuid(resource_company_id):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=not_found_detail,
        )


def can_manage_company_users(actor: UserProfileResponse) -> bool:
    if is_platform_admin(actor):
        return True
    try:
        return EnterpriseRole(str(actor.role)) in _COMPANY_USER_MANAGERS
    except ValueError:
        return False


def require_platform_admin(actor: UserProfileResponse) -> None:
    if not is_platform_admin(actor):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required.",
        )
