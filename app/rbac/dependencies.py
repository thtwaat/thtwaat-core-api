"""
app/rbac/dependencies.py

FastAPI dependencies for permission-based authorization.
"""

from typing import Callable
from fastapi import HTTPException, status, Depends

from app.rbac.enums import EnterpriseRole, Permission
from app.rbac.policy import ROLE_PERMISSIONS


class RequirePermission:
    """
    FastAPI dependency to enforce RBAC permissions.
    Usage:
        @router.post("/", dependencies=[Depends(RequirePermission(Permission.APPS_CREATE))])
    """

    def __init__(self, required_permission: Permission):
        self.required_permission = required_permission

    def __call__(self, current_user_role: str) -> None:
        """
        Validates if the user's role has the required permission.
        NOTE: Since existing modules were not modified, current_user_role is passed as a string.
        In a fully integrated setup, this would accept the User profile from Auth directly.
        """
        try:
            role_enum = EnterpriseRole(current_user_role)
        except ValueError:
            # If the role string doesn't match our new EnterpriseRole, deny access
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user_role}' is not recognized in the RBAC policy.",
            )

        allowed_permissions = ROLE_PERMISSIONS.get(role_enum, set())
        
        if self.required_permission not in allowed_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have the necessary permission: {self.required_permission.value}",
            )
