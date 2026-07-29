"""
app/rbac/policy.py

Maps EnterpriseRoles to their respective Permissions.
"""

from app.rbac.enums import EnterpriseRole, Permission

# Role to Permission mapping
ROLE_PERMISSIONS: dict[EnterpriseRole, set[Permission]] = {
    
    EnterpriseRole.SUPER_ADMIN: set(Permission), # All permissions
    
    EnterpriseRole.COMPANY_OWNER: {
        Permission.APPS_CREATE, Permission.APPS_READ, Permission.APPS_UPDATE, Permission.APPS_DELETE,
        Permission.USERS_CREATE, Permission.USERS_READ, Permission.USERS_UPDATE, Permission.USERS_DELETE,
        Permission.COMPANY_READ, Permission.COMPANY_UPDATE,
        Permission.AGENTS_READ, Permission.AGENTS_CREATE, Permission.AGENTS_UPDATE,
        Permission.AGENTS_PUBLISH, Permission.AGENTS_MANAGE_KEYS,
        Permission.DOMAINS_READ, Permission.DOMAINS_MANAGE,
        Permission.TEMPLATES_READ, Permission.TEMPLATES_MANAGE,
        Permission.BRANDING_READ, Permission.BRANDING_MANAGE,
    },
    
    EnterpriseRole.ADMIN: {
        Permission.APPS_CREATE, Permission.APPS_READ, Permission.APPS_UPDATE, Permission.APPS_DELETE,
        Permission.USERS_CREATE, Permission.USERS_READ, Permission.USERS_UPDATE, Permission.USERS_DELETE,
        Permission.COMPANY_READ,
        Permission.AGENTS_READ, Permission.AGENTS_CREATE, Permission.AGENTS_UPDATE,
        Permission.AGENTS_PUBLISH, Permission.AGENTS_MANAGE_KEYS,
        Permission.DOMAINS_READ, Permission.DOMAINS_MANAGE,
        Permission.TEMPLATES_READ, Permission.TEMPLATES_MANAGE,
        Permission.BRANDING_READ, Permission.BRANDING_MANAGE,
    },
    
    EnterpriseRole.MANAGER: {
        Permission.APPS_READ, Permission.APPS_UPDATE,
        Permission.USERS_READ,
        Permission.COMPANY_READ,
        Permission.AGENTS_READ, Permission.AGENTS_CREATE, Permission.AGENTS_UPDATE,
        Permission.DOMAINS_READ,
        Permission.TEMPLATES_READ,
        Permission.BRANDING_READ,
    },
    
    EnterpriseRole.DEVELOPER: {
        Permission.APPS_CREATE, Permission.APPS_READ, Permission.APPS_UPDATE,
        Permission.COMPANY_READ,
        Permission.AGENTS_READ, Permission.AGENTS_CREATE, Permission.AGENTS_UPDATE,
        Permission.AGENTS_MANAGE_KEYS,
        Permission.DOMAINS_READ, Permission.DOMAINS_MANAGE,
        Permission.TEMPLATES_READ, Permission.TEMPLATES_MANAGE,
        Permission.BRANDING_READ,
    },
    
    EnterpriseRole.EMPLOYEE: {
        Permission.APPS_READ,
        Permission.USERS_READ,
        Permission.COMPANY_READ,
        Permission.AGENTS_READ,
        Permission.DOMAINS_READ,
        Permission.TEMPLATES_READ,
        Permission.BRANDING_READ,
    },
    
    EnterpriseRole.VIEWER: {
        Permission.APPS_READ,
        Permission.USERS_READ,
        Permission.COMPANY_READ,
        Permission.AGENTS_READ,
        Permission.DOMAINS_READ,
        Permission.TEMPLATES_READ,
        Permission.BRANDING_READ,
    }
}
