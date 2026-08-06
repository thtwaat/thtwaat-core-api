/** Role helpers aligned with app/rbac/policy.py */

const TEMPLATE_MANAGE_ROLES = new Set([
  "super_admin",
  "company_owner",
  "admin",
  "developer"
]);

const STUDIO_DELETE_ROLES = new Set(["super_admin", "company_owner", "admin"]);

export function canManageTemplates(role?: string | null): boolean {
  return Boolean(role && TEMPLATE_MANAGE_ROLES.has(role));
}

export function canPlatformAdmin(role?: string | null): boolean {
  return role === "super_admin";
}

export function canAccessAdmin(role?: string | null): boolean {
  return canManageTemplates(role) || canPlatformAdmin(role);
}

/** Webhook CRUD — aligned with developer/admin roles that manage integrations */
export function canManageWebhooks(role?: string | null): boolean {
  return canManageTemplates(role);
}

/** AI provider status board — same operator roles as integrations */
export function canViewProviders(role?: string | null): boolean {
  return canManageTemplates(role);
}

/** Studio / Agent delete — owners/admins only (matches can_manage_company_users). */
export function canDeleteStudioProjects(role?: string | null): boolean {
  return Boolean(role && STUDIO_DELETE_ROLES.has(role));
}

/** Agent soft-delete — company_owner / admin / super_admin only. */
export function canDeleteAgents(role?: string | null): boolean {
  return Boolean(role && STUDIO_DELETE_ROLES.has(role));
}
