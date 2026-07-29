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

    # Agents / Publish
    AGENTS_READ         = "agents:read"
    AGENTS_CREATE       = "agents:create"
    AGENTS_UPDATE       = "agents:update"
    AGENTS_PUBLISH      = "agents:publish"
    AGENTS_MANAGE_KEYS  = "agents:manage_keys"

    # Domains
    DOMAINS_READ   = "domains:read"
    DOMAINS_MANAGE = "domains:manage"

    # Templates / Marketplace
    TEMPLATES_READ   = "templates:read"
    TEMPLATES_MANAGE = "templates:manage"

    # White-label branding
    BRANDING_READ   = "branding:read"
    BRANDING_MANAGE = "branding:manage"

    # Enterprise administration
    ENTERPRISE_READ       = "enterprise:read"
    ENTERPRISE_MANAGE     = "enterprise:manage"
    ENTERPRISE_SECURITY   = "enterprise:security"
    ENTERPRISE_AUDIT      = "enterprise:audit"
    ENTERPRISE_COMPLIANCE = "enterprise:compliance"
    ENTERPRISE_REPORTS    = "enterprise:reports"
    
    # Platform (Super Admin only)
    PLATFORM_ADMIN = "platform:admin"
