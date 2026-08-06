"""Studio Template Registry — maps product needs to existing THTWAAT modules.

No codegen. Every entry points at a platform module and/or marketplace template.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class RegistryEntry:
    key: str
    label: str
    category: str  # foundation | surface | ai | commerce | ops
    platform_ref: Optional[str]  # existing codebase path / package
    marketplace_templates: Tuple[str, ...] = ()
    depends_on: Tuple[str, ...] = ()
    aliases: Tuple[str, ...] = ()
    description: str = ""
    custom_allowed: bool = False  # only true for extensibility hooks


# Canonical registry — reuse Auth, Billing, AI Gateway, Marketplace, Knowledge,
# Agents, Publisher, Admin. Do not invent parallel modules.
TEMPLATE_REGISTRY: Dict[str, RegistryEntry] = {
    "authentication": RegistryEntry(
        key="authentication",
        label="Authentication",
        category="foundation",
        platform_ref="app/auth",
        depends_on=(),
        aliases=("auth", "authentication", "login", "jwt", "oauth"),
        description="Email/password, JWT, MFA — existing Auth module",
    ),
    "rbac": RegistryEntry(
        key="rbac",
        label="RBAC",
        category="foundation",
        platform_ref="app/auth",
        depends_on=("authentication",),
        aliases=("rbac", "roles", "permissions", "acl"),
        description="Roles and permissions via Auth tenancy",
    ),
    "database": RegistryEntry(
        key="database",
        label="Database",
        category="foundation",
        platform_ref="app/database",
        depends_on=("authentication",),
        aliases=("database", "db", "postgres", "tables", "schema"),
        description="PostgreSQL schema via Alembic — no parallel DB stack",
    ),
    "storage": RegistryEntry(
        key="storage",
        label="Storage",
        category="foundation",
        platform_ref="app/storage",
        depends_on=("authentication",),
        aliases=("storage", "uploads", "files", "s3", "blob"),
        description="Existing Storage module for uploads/documents",
    ),
    "notifications": RegistryEntry(
        key="notifications",
        label="Notifications",
        category="ops",
        platform_ref="app/notifications",
        depends_on=("authentication",),
        aliases=("notifications", "email", "sms", "push"),
        description="Existing Notifications module",
    ),
    "billing": RegistryEntry(
        key="billing",
        label="Billing",
        category="commerce",
        platform_ref="app/payments",
        depends_on=("authentication", "database"),
        aliases=("billing", "subscriptions", "plans", "invoices", "metering"),
        description="Plans, subscriptions, invoices — existing Billing",
    ),
    "payments": RegistryEntry(
        key="payments",
        label="Payments",
        category="commerce",
        platform_ref="app/payments",
        depends_on=("billing",),
        aliases=("payments", "stripe", "razorpay", "checkout"),
        description="Stripe/Razorpay providers under Billing",
    ),
    "admin": RegistryEntry(
        key="admin",
        label="Admin",
        category="surface",
        platform_ref="app/monitoring",
        depends_on=("authentication", "rbac"),
        aliases=("admin", "ops", "superadmin", "company_owner"),
        description="Admin/ops surfaces — reuse Admin + owner roles",
    ),
    "dashboard": RegistryEntry(
        key="dashboard",
        label="Dashboard",
        category="surface",
        platform_ref="apps/templates/saas",
        marketplace_templates=("saas-starter", "ai-saas-starter", "crm-starter"),
        depends_on=("authentication", "rbac", "database"),
        aliases=("dashboard", "app shell", "console"),
        description="SaaS dashboard shell from Marketplace templates",
    ),
    "landing_page": RegistryEntry(
        key="landing_page",
        label="Landing Page",
        category="surface",
        platform_ref="apps/templates/landing",
        marketplace_templates=("landing-page-starter", "ai-landing-starter"),
        depends_on=(),
        aliases=("landing", "landing page", "marketing", "website home"),
        description="Marketing/landing templates from Marketplace",
    ),
    "marketplace": RegistryEntry(
        key="marketplace",
        label="Marketplace",
        category="commerce",
        platform_ref="app/marketplace",
        depends_on=("authentication",),
        aliases=("marketplace", "templates store", "catalog"),
        description="Existing Marketplace catalog — do not duplicate",
    ),
    "knowledge": RegistryEntry(
        key="knowledge",
        label="Knowledge",
        category="ai",
        platform_ref="app/agent_platform/knowledge",
        depends_on=("authentication", "storage"),
        aliases=("knowledge", "rag", "kb", "docs pack"),
        description="Existing Knowledge / RAG module",
    ),
    "ai_agent": RegistryEntry(
        key="ai_agent",
        label="AI Agent",
        category="ai",
        platform_ref="app/agent_platform",
        depends_on=("authentication", "knowledge"),
        aliases=("ai agent", "agents", "ai gateway", "chat", "assistant"),
        description="Agents + AI Gateway — no parallel AI stack",
    ),
    "widget": RegistryEntry(
        key="widget",
        label="Widget",
        category="ai",
        platform_ref="sdk/widget",
        depends_on=("ai_agent",),
        aliases=("widget", "embed", "chat widget"),
        description="Existing embeddable Widget SDK",
    ),
    "publisher": RegistryEntry(
        key="publisher",
        label="Publisher",
        category="ai",
        platform_ref="app/agent_platform/publish",
        depends_on=("ai_agent", "marketplace"),
        aliases=("publisher", "publish", "agent store"),
        description="Existing Publisher portal for agent packaging",
    ),
    "analytics": RegistryEntry(
        key="analytics",
        label="Analytics",
        category="ops",
        platform_ref="app/monitoring",
        depends_on=("authentication", "database"),
        aliases=("analytics", "metrics", "usage", "telemetry"),
        description="Monitoring / usage analytics surfaces",
    ),
}


# Preferred build-plan phase order (keys may expand into registry entries).
BUILD_PHASE_ORDER: Tuple[str, ...] = (
    "authentication",
    "rbac",
    "database",
    "storage",
    "notifications",
    "billing",
    "payments",
    "admin",
    "dashboard",
    "landing_page",
    "marketplace",
    "knowledge",
    "ai_agent",
    "widget",
    "publisher",
    "analytics",
)

# Phase buckets for human-readable execution plan (Auth → … → Deployment placeholder).
BUILD_PHASE_LABELS: Dict[str, str] = {
    "authentication": "Auth",
    "rbac": "Auth",
    "database": "Database",
    "storage": "Database",
    "billing": "Billing",
    "payments": "Billing",
    "dashboard": "Dashboard",
    "admin": "Dashboard",
    "ai_agent": "AI",
    "knowledge": "AI",
    "widget": "AI",
    "publisher": "AI",
    "landing_page": "Website",
    "marketplace": "Website",
    "notifications": "Ops",
    "analytics": "Ops",
}


def get_registry_entry(key: str) -> Optional[RegistryEntry]:
    return TEMPLATE_REGISTRY.get(key)


def resolve_alias(name: str) -> Optional[str]:
    """Map a free-form blueprint module/page name to a registry key."""
    needle = (name or "").strip().lower()
    if not needle:
        return None
    if needle in TEMPLATE_REGISTRY:
        return needle
    # normalize separators
    compact = needle.replace("-", " ").replace("_", " ")
    for key, entry in TEMPLATE_REGISTRY.items():
        if compact == entry.label.lower():
            return key
        if compact in entry.aliases or needle in entry.aliases:
            return key
        for alias in entry.aliases:
            if alias in compact or compact in alias:
                return key
    # common compound forms
    if "ai gateway" in compact or compact == "ai":
        return "ai_agent"
    if "landing" in compact:
        return "landing_page"
    return None


def list_registry() -> List[RegistryEntry]:
    return [TEMPLATE_REGISTRY[k] for k in BUILD_PHASE_ORDER if k in TEMPLATE_REGISTRY]
