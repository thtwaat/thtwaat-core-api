"""Role policy for user creation (public signup vs platform admin)."""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status as http_status

from app.rbac.enums import EnterpriseRole

# Public / unauthenticated signup may only mint these tenant roles.
# Everything else (super_admin, admin, manager, …) is privileged.
PUBLIC_SIGNUP_ROLES: frozenset[EnterpriseRole] = frozenset(
    {
        EnterpriseRole.COMPANY_OWNER,
        EnterpriseRole.EMPLOYEE,
    }
)


def assert_create_role_allowed(
    role: EnterpriseRole,
    *,
    allow_privileged: bool,
) -> None:
    """
    Enforce role policy for POST /users.

    - Public signup (and non–platform-admin callers): only PUBLIC_SIGNUP_ROLES.
    - Platform admins (PLATFORM_ADMIN permission): any EnterpriseRole.
    """
    if allow_privileged:
        return
    if role not in PUBLIC_SIGNUP_ROLES:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{role.value}' is not allowed for public signup. "
                f"Allowed roles: {', '.join(sorted(r.value for r in PUBLIC_SIGNUP_ROLES))}."
            ),
        )
