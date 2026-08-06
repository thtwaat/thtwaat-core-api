"""Studio Frontend Generator — build plan → reusable frontend manifest (no codegen / no deploy)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.product_generator.analyzer import NAV_BY_TYPE
from app.studio.schemas import (
    BlueprintWarning,
    ComposedModule,
    FrontendCrudSpec,
    FrontendFormField,
    FrontendFormSpec,
    FrontendManifest,
    FrontendNavItem,
    FrontendPageSpec,
    FrontendReuseRef,
    FrontendRoute,
    FrontendSummary,
    ProductBlueprint,
)


# Map composed module keys → existing SaaS UI (apps/templates/saas)
REUSE_PAGE_CATALOG: Dict[str, Dict[str, Any]] = {
    "authentication": {
        "page_id": "login",
        "title": "Login",
        "route": "/login",
        "layout": "auth",
        "auth": "public",
        "file": "app/login/page.tsx",
        "icon": "LogIn",
        "nav": False,
    },
    "dashboard": {
        "page_id": "dashboard",
        "title": "Overview",
        "route": "/app",
        "layout": "app",
        "auth": "session",
        "file": "app/app/page.tsx",
        "icon": "LayoutDashboard",
        "nav": True,
    },
    "billing": {
        "page_id": "billing",
        "title": "Billing",
        "route": "/app/billing",
        "layout": "app",
        "auth": "session",
        "file": "app/app/billing/page.tsx",
        "icon": "CreditCard",
        "nav": True,
    },
    "payments": {
        "page_id": "billing",
        "title": "Billing",
        "route": "/app/billing",
        "layout": "app",
        "auth": "session",
        "file": "app/app/billing/page.tsx",
        "icon": "CreditCard",
        "nav": True,
        "alias_of": "billing",
    },
    "admin": {
        "page_id": "admin",
        "title": "Admin",
        "route": "/app/admin",
        "layout": "app",
        "auth": "session",
        "file": "app/app/admin/page.tsx",
        "icon": "Shield",
        "nav": True,
    },
    "ai_agent": {
        "page_id": "agents",
        "title": "Agents",
        "route": "/app/agents",
        "layout": "app",
        "auth": "session",
        "file": "app/app/agents/page.tsx",
        "icon": "Bot",
        "nav": True,
    },
    "knowledge": {
        "page_id": "knowledge",
        "title": "Knowledge",
        "route": "/app/knowledge",
        "layout": "app",
        "auth": "session",
        "file": "app/app/knowledge/page.tsx",
        "icon": "Library",
        "nav": True,
    },
    "marketplace": {
        "page_id": "marketplace",
        "title": "Marketplace",
        "route": "/app/templates",
        "layout": "app",
        "auth": "session",
        "file": "app/app/templates/page.tsx",
        "icon": "Store",
        "nav": True,
    },
    "publisher": {
        "page_id": "publisher",
        "title": "Publisher",
        "route": "/app/publisher",
        "layout": "app",
        "auth": "session",
        "file": "app/app/publisher/page.tsx",
        "icon": "Upload",
        "nav": True,
    },
    "analytics": {
        "page_id": "analytics",
        "title": "Analytics",
        "route": "/app/analytics",
        "layout": "app",
        "auth": "session",
        "file": "app/app/analytics/page.tsx",
        "icon": "BarChart3",
        "nav": True,
    },
    "notifications": {
        "page_id": "inbox",
        "title": "Inbox",
        "route": "/app/inbox",
        "layout": "app",
        "auth": "session",
        "file": "app/app/inbox/page.tsx",
        "icon": "Inbox",
        "nav": True,
    },
    "widget": {
        "page_id": "agents_playground",
        "title": "Agent Playground",
        "route": "/app/agents",
        "layout": "app",
        "auth": "session",
        "file": "app/app/agents/[id]/playground/page.tsx",
        "icon": "MessageSquare",
        "nav": False,
    },
    "landing_page": {
        "page_id": "landing",
        "title": "Landing",
        "route": "/",
        "layout": "marketing",
        "auth": "public",
        "file": "apps/templates/landing",
        "icon": "Home",
        "nav": False,
    },
    "storage": {
        "page_id": "settings",
        "title": "Settings",
        "route": "/app/settings",
        "layout": "app",
        "auth": "session",
        "file": "app/app/settings/page.tsx",
        "icon": "Settings",
        "nav": False,
    },
    "rbac": {
        "page_id": "admin",
        "title": "Admin",
        "route": "/app/admin",
        "layout": "app",
        "auth": "session",
        "file": "app/app/admin/page.tsx",
        "icon": "Shield",
        "nav": False,
        "alias_of": "admin",
    },
    "database": {
        "page_id": "dashboard",
        "title": "Overview",
        "route": "/app",
        "layout": "app",
        "auth": "session",
        "file": "app/app/page.tsx",
        "icon": "LayoutDashboard",
        "nav": False,
        "alias_of": "dashboard",
    },
}

# Blueprint page name → reuse catalog key (when module also selected)
PAGE_NAME_TO_MODULE: Dict[str, str] = {
    "login": "authentication",
    "signup": "authentication",
    "register": "authentication",
    "landing": "landing_page",
    "home": "landing_page",
    "dashboard": "dashboard",
    "overview": "dashboard",
    "admin": "admin",
    "billing": "billing",
    "payments": "payments",
    "agents": "ai_agent",
    "ai": "ai_agent",
    "knowledge": "knowledge",
    "marketplace": "marketplace",
    "templates": "marketplace",
    "publisher": "publisher",
    "analytics": "analytics",
    "inbox": "notifications",
    "settings": "storage",
}

SKIP_CUSTOM_PAGES = {
    "login",
    "signup",
    "register",
    "landing",
    "home",
    "dashboard",
    "overview",
    "admin",
    "billing",
    "payments",
    "agents",
    "knowledge",
    "marketplace",
    "templates",
    "publisher",
    "analytics",
    "inbox",
    "settings",
    "website",
}


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s[:64] or "page"


def _singular(name: str) -> str:
    low = name.strip().lower()
    if low.endswith("ies"):
        return low[:-3] + "y"
    if low.endswith("s") and not low.endswith("ss"):
        return low[:-1]
    return low


def _table_for_page(page: str, tables: List[str]) -> Optional[str]:
    slug = _slug(page).replace("-", "_")
    singular = _singular(page).replace(" ", "_").replace("-", "_")
    for t in tables:
        tl = t.lower()
        if tl == slug or tl == singular or tl.rstrip("s") == singular:
            return t
    # fuzzy contains
    for t in tables:
        if singular in t.lower() or t.lower() in singular:
            return t
    return None


def _default_fields(entity: str, table: Optional[str]) -> List[FrontendFormField]:
    base = [
        FrontendFormField(name="id", type="uuid", required=False, label="ID", list_column=True),
        FrontendFormField(
            name="name" if entity != "patient" else "full_name",
            type="string",
            required=True,
            label="Name",
            list_column=True,
        ),
        FrontendFormField(name="status", type="select", required=False, label="Status", list_column=True),
        FrontendFormField(name="notes", type="textarea", required=False, label="Notes", list_column=False),
        FrontendFormField(
            name="created_at", type="datetime", required=False, label="Created", list_column=True
        ),
    ]
    if table and "appointment" in table.lower():
        return [
            FrontendFormField(name="id", type="uuid", required=False, label="ID", list_column=True),
            FrontendFormField(name="patient_id", type="uuid", required=True, label="Patient", list_column=True),
            FrontendFormField(
                name="scheduled_at", type="datetime", required=True, label="Scheduled", list_column=True
            ),
            FrontendFormField(name="status", type="select", required=True, label="Status", list_column=True),
            FrontendFormField(name="notes", type="textarea", required=False, label="Notes", list_column=False),
        ]
    if table and "lead" in table.lower():
        return [
            FrontendFormField(name="id", type="uuid", required=False, label="ID", list_column=True),
            FrontendFormField(name="full_name", type="string", required=True, label="Name", list_column=True),
            FrontendFormField(name="email", type="email", required=True, label="Email", list_column=True),
            FrontendFormField(name="stage", type="select", required=False, label="Stage", list_column=True),
        ]
    return base


def _dashboard_cards(
    blueprint: ProductBlueprint, module_keys: Set[str]
) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for mod in blueprint.dashboard_modules[:6]:
        cards.append(
            {
                "id": f"card_{_slug(mod)}",
                "type": "module",
                "title": mod,
                "binding": f"dashboard.{_slug(mod)}",
            }
        )
    if "ai_agent" in module_keys:
        cards.append(
            {
                "id": "card_agents",
                "type": "stat",
                "title": "Agents",
                "binding": "agents.count",
            }
        )
    if "billing" in module_keys:
        cards.append(
            {
                "id": "card_revenue",
                "type": "stat",
                "title": "Revenue",
                "binding": "billing.mrr",
            }
        )
    if "knowledge" in module_keys:
        cards.append(
            {
                "id": "card_knowledge",
                "type": "stat",
                "title": "Knowledge packs",
                "binding": "knowledge.docs",
            }
        )
    if not cards:
        cards.append(
            {
                "id": "card_usage",
                "type": "stat",
                "title": "Usage",
                "binding": "usage.ai_messages",
            }
        )
    return cards


def _reuse_page_from_catalog(
    module_key: str, *, reason: str
) -> Optional[FrontendPageSpec]:
    meta = REUSE_PAGE_CATALOG.get(module_key)
    if not meta:
        return None
    return FrontendPageSpec(
        id=str(meta["page_id"]),
        title=str(meta["title"]),
        kind="reuse",
        route=str(meta["route"]),
        layout=str(meta["layout"]),
        auth=str(meta["auth"]),
        module_key=module_key,
        reuse=FrontendReuseRef(
            kind="existing_page",
            path=str(meta["file"]),
            route=str(meta["route"]),
            module_key=module_key,
            component=None,
        ),
        reason=reason,
        responsive=True,
        cards=_dashboard_cards(
            ProductBlueprint(), {module_key}
        )
        if meta["page_id"] == "dashboard"
        else [],
        preview={
            "blocks": ["page_header", "content"],
            "reuse": True,
            "source": meta["file"],
        },
    )


def generate_page_manifest(
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
) -> Tuple[List[FrontendPageSpec], List[FrontendFormSpec], List[BlueprintWarning]]:
    module_keys = {m.key for m in modules}
    pages: List[FrontendPageSpec] = []
    forms: List[FrontendFormSpec] = []
    warnings: List[BlueprintWarning] = []
    seen_page_ids: Set[str] = set()

    def add_page(page: FrontendPageSpec) -> None:
        if page.id in seen_page_ids:
            return
        seen_page_ids.add(page.id)
        pages.append(page)

    # Always-reuse modules from build plan
    for mod in modules:
        if mod.key.startswith("custom:"):
            continue
        if mod.key in {"deployment"}:
            continue
        catalog = REUSE_PAGE_CATALOG.get(mod.key)
        if not catalog:
            continue
        if catalog.get("alias_of") and catalog["alias_of"] in module_keys:
            # Prefer canonical page (e.g. payments → billing)
            continue
        page = _reuse_page_from_catalog(
            mod.key, reason=f"Reuse existing UI for {mod.label}"
        )
        if page:
            if page.id == "dashboard":
                page.cards = _dashboard_cards(blueprint, module_keys)
            add_page(page)
            if mod.key == "authentication":
                forms.append(
                    FrontendFormSpec(
                        id="login_form",
                        page_id="login",
                        title="Sign in",
                        reuse=True,
                        fields=[
                            FrontendFormField(name="email", type="email", required=True, label="Email"),
                            FrontendFormField(
                                name="password", type="password", required=True, label="Password"
                            ),
                        ],
                        submit_label="Sign in",
                    )
                )

    # Ensure dashboard if saas-like
    if "dashboard" not in seen_page_ids and (
        "dashboard" in module_keys
        or (blueprint.product_type or "").lower() in {"saas", "crm", "helpdesk"}
    ):
        page = _reuse_page_from_catalog("dashboard", reason="SaaS shell requires Overview")
        if page:
            page.cards = _dashboard_cards(blueprint, module_keys)
            add_page(page)

    # Settings always useful for app shell products
    if any(p.layout == "app" for p in pages) and "settings" not in seen_page_ids:
        add_page(
            FrontendPageSpec(
                id="settings",
                title="Settings",
                kind="reuse",
                route="/app/settings",
                layout="app",
                auth="session",
                module_key="storage",
                reuse=FrontendReuseRef(
                    kind="existing_page",
                    path="app/app/settings/page.tsx",
                    route="/app/settings",
                    module_key="storage",
                ),
                reason="Reuse existing Settings page",
                responsive=True,
                preview={"blocks": ["settings_form"], "reuse": True},
            )
        )

    # Custom / domain CRUD pages from blueprint pages + custom modules
    custom_labels: List[str] = []
    for mod in modules:
        if mod.key.startswith("custom:"):
            custom_labels.append(mod.label)
    for raw_page in blueprint.pages:
        low = raw_page.strip().lower()
        if low in SKIP_CUSTOM_PAGES:
            continue
        mapped = PAGE_NAME_TO_MODULE.get(low)
        if mapped and mapped in module_keys:
            continue
        custom_labels.append(raw_page.strip())

    # Dedupe custom labels case-insensitively
    seen_custom: Set[str] = set()
    for label in custom_labels:
        key = label.lower()
        if key in seen_custom:
            continue
        seen_custom.add(key)
        page_id = f"crud_{_slug(label)}"
        table = _table_for_page(label, blueprint.database_tables)
        entity = _singular(label)
        fields = _default_fields(entity, table)
        crud = FrontendCrudSpec(
            entity=entity,
            table=table or _slug(label).replace("-", "_"),
            operations=["list", "create", "update", "delete"],
            fields=fields,
            table_columns=[f.name for f in fields if f.list_column],
            form_id=f"form_{_slug(label)}",
        )
        forms.append(
            FrontendFormSpec(
                id=crud.form_id or f"form_{_slug(label)}",
                page_id=page_id,
                title=f"Save {entity}",
                reuse=False,
                fields=fields,
                submit_label=f"Save {entity}",
            )
        )
        add_page(
            FrontendPageSpec(
                id=page_id,
                title=label,
                kind="generated_spec",
                route=f"/app/custom/{_slug(label)}",
                layout="app",
                auth="session",
                module_key=f"custom:{_slug(label).replace('-', '_')}",
                reuse=None,
                reason=f"Custom CRUD screen for “{label}” (no existing page)",
                responsive=True,
                crud=crud,
                layout_slots=["page_header", "filters", "data_table", "form_drawer"],
                preview={
                    "blocks": ["page_header", "data_table", "form_drawer"],
                    "sample_rows": [
                        {f.name: ("Sample" if f.type == "string" else None) for f in fields if f.list_column}
                    ],
                    "empty_state": {"title": f"No {label.lower()} yet"},
                },
            )
        )

    reused = sum(1 for p in pages if p.kind == "reuse")
    if reused == 0:
        warnings.append(
            BlueprintWarning(
                code="frontend_no_reuse",
                severity="warn",
                message="No existing SaaS pages were mapped — check the build plan modules.",
                field="pages",
            )
        )
    return pages, forms, warnings


def generate_navigation(pages: List[FrontendPageSpec]) -> List[FrontendNavItem]:
    items: List[FrontendNavItem] = []
    seen_routes: Set[str] = set()
    # Prefer stable order: dashboard, customs, then known modules
    priority = {
        "dashboard": 0,
        "agents": 1,
        "knowledge": 2,
        "marketplace": 3,
        "billing": 4,
        "analytics": 5,
        "inbox": 6,
        "publisher": 7,
        "admin": 8,
        "settings": 90,
    }
    nav_pages = [p for p in pages if p.layout == "app" and p.auth == "session"]
    nav_pages.sort(key=lambda p: (priority.get(p.id, 50), p.title.lower()))
    for page in nav_pages:
        if page.route in seen_routes:
            continue
        # Skip alias playground-only
        if page.id == "agents_playground":
            continue
        seen_routes.add(page.route)
        icon = "LayoutDashboard"
        if page.module_key and page.module_key in REUSE_PAGE_CATALOG:
            icon = str(REUSE_PAGE_CATALOG[page.module_key].get("icon") or icon)
        elif page.kind == "generated_spec":
            icon = "Table"
        items.append(
            FrontendNavItem(
                id=page.id,
                label=page.title,
                route=page.route,
                icon=icon,
                page_id=page.id,
                reuse=page.kind == "reuse",
            )
        )
    # Fallback from product-type nav labels if empty
    if not items:
        for label in NAV_BY_TYPE.get("saas", ["Dashboard"]):
            items.append(
                FrontendNavItem(
                    id=_slug(label),
                    label=label,
                    route="/app",
                    icon="LayoutDashboard",
                    page_id="dashboard",
                    reuse=True,
                )
            )
    return items


def generate_routes(pages: List[FrontendPageSpec]) -> List[FrontendRoute]:
    routes: List[FrontendRoute] = []
    seen: Set[str] = set()
    for page in pages:
        if page.route in seen:
            continue
        seen.add(page.route)
        routes.append(
            FrontendRoute(
                path=page.route,
                page_id=page.id,
                layout=page.layout,
                auth=page.auth,
                reuse=page.kind == "reuse",
            )
        )
    return routes


def summarize_frontend(
    pages: List[FrontendPageSpec],
    *,
    nav: List[FrontendNavItem],
    routes: List[FrontendRoute],
) -> FrontendSummary:
    reused_pages = sum(1 for p in pages if p.kind == "reuse")
    generated = sum(1 for p in pages if p.kind == "generated_spec")
    total = max(len(pages), 1)
    reuse_pct = round(100.0 * reused_pages / total, 1)
    warnings: List[BlueprintWarning] = []
    if generated and reuse_pct < 50:
        warnings.append(
            BlueprintWarning(
                code="frontend_low_reuse",
                severity="warn",
                message=f"Frontend reuse is {reuse_pct}% — prefer existing Dashboard/Auth/Billing/Agents pages.",
                field="reuse_percent",
            )
        )
    if not any(p.id == "login" or p.module_key == "authentication" for p in pages):
        warnings.append(
            BlueprintWarning(
                code="frontend_missing_auth_ui",
                severity="info",
                message="No Login page mapped — AuthShell reuse recommended for SaaS products.",
                field="pages",
            )
        )
    return FrontendSummary(
        page_count=len(pages),
        reuse_page_count=reused_pages,
        generated_page_count=generated,
        nav_item_count=len(nav),
        route_count=len(routes),
        form_count=0,  # filled by caller
        reuse_percent=reuse_pct,
        estimated_custom_work="none"
        if generated == 0
        else ("low" if generated <= 2 else "medium" if generated <= 5 else "high"),
        warnings=warnings,
    )


def generate_frontend_manifest(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    project_title: str,
    blueprint_version: int,
    build_plan_version: int,
) -> FrontendManifest:
    pages, forms, page_warnings = generate_page_manifest(blueprint, modules)
    nav = generate_navigation(pages)
    routes = generate_routes(pages)
    summary = summarize_frontend(pages, nav=nav, routes=routes)
    summary.form_count = len(forms)
    summary.warnings = page_warnings + summary.warnings

    layouts = [
        {
            "id": "auth",
            "component": "AuthShell",
            "reuse": {
                "kind": "layout",
                "path": "components/layout/auth-shell.tsx",
            },
        },
        {
            "id": "app",
            "component": "AppShell",
            "reuse": {
                "kind": "layout",
                "path": "components/layout/app-shell.tsx",
            },
            "nav_ref": "main",
        },
        {
            "id": "marketing",
            "component": "LandingTemplate",
            "reuse": {
                "kind": "layout",
                "path": "apps/templates/landing",
            },
        },
    ]

    return FrontendManifest(
        schema_version=1,
        product_name=project_title,
        industry=blueprint.industry,
        product_type=blueprint.product_type,
        theme={
            "mode": "light",
            "primary": "#0F766E",
            "accent": "#99F6E4",
            "shell": "app_shell",
        },
        layouts=layouts,
        design_system={
            "button": "components/ui/button.tsx",
            "card": "components/ui/card.tsx",
            "badge": "components/ui/card.tsx#Badge",
            "input": "components/ui/input.tsx",
            "page_header": "components/ui/misc.tsx#PageHeader",
            "empty_state": "components/ui/misc.tsx#EmptyState",
            "app_shell": "components/layout/app-shell.tsx",
            "auth_shell": "components/layout/auth-shell.tsx",
        },
        nav=nav,
        routes=routes,
        pages=pages,
        forms=forms,
        dashboard_cards=_dashboard_cards(blueprint, {m.key for m in modules}),
        responsive={"breakpoints": ["sm", "md", "lg", "xl"], "mobile_nav": True},
        summary=summary,
        traceability={
            "blueprint_version": blueprint_version,
            "build_plan_version": build_plan_version,
            "composed_modules": [m.key for m in modules],
            "reuse_percent": summary.reuse_percent,
        },
        warnings=summary.warnings,
    )
