"""
app/rbac/enums.py

Defines Enterprise Roles and granular Permissions.
"""

import enum

class EnterpriseRole(str, enum.Enum):
    """Standardized roles for enterprise RBAC."""
    SUPER_ADMIN   = "super_admin"    # Platform level super admin
    COMPANY_OWNER = "company_owner"  # Tenant owner
    ADMIN         = "admin"          # Tenant admin
    MANAGER       = "manager"        # Department/team manager
    DEVELOPER     = "developer"      # Technical staff (API keys, webhooks)
    EMPLOYEE      = "employee"       # Standard user
    VIEWER        = "viewer"         # Read-only access


class Permission(str, enum.Enum):
    """Granular permissions for the system."""
    
    # Apps
    APPS_CREATE = "apps:create"
    APPS_READ   = "apps:read"
    APPS_UPDATE = "apps:update"
    APPS_DELETE = "apps:delete"
    
    # Users
    USERS_CREATE = "users:create"
    USERS_READ   = "users:read"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    
    # Companies
    COMPANY_READ   = "company:read"
    COMPANY_UPDATE = "company:update"
    
    # Platform (Super Admin only)
    PLATFORM_ADMIN = "platform:admin"
