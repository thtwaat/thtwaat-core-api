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
    },
    
    EnterpriseRole.ADMIN: {
        Permission.APPS_CREATE, Permission.APPS_READ, Permission.APPS_UPDATE, Permission.APPS_DELETE,
        Permission.USERS_CREATE, Permission.USERS_READ, Permission.USERS_UPDATE, Permission.USERS_DELETE,
        Permission.COMPANY_READ,
    },
    
    EnterpriseRole.MANAGER: {
        Permission.APPS_READ, Permission.APPS_UPDATE,
        Permission.USERS_READ,
        Permission.COMPANY_READ,
    },
    
    EnterpriseRole.DEVELOPER: {
        Permission.APPS_CREATE, Permission.APPS_READ, Permission.APPS_UPDATE,
        Permission.COMPANY_READ,
    },
    
    EnterpriseRole.EMPLOYEE: {
        Permission.APPS_READ,
        Permission.USERS_READ,
        Permission.COMPANY_READ,
    },
    
    EnterpriseRole.VIEWER: {
        Permission.APPS_READ,
        Permission.USERS_READ,
        Permission.COMPANY_READ,
    }
}
