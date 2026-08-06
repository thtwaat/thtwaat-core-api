"""Module Composer — blueprint → reusable module plan (no codegen / no deploy)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from app.product_generator.service import CATEGORY_TEMPLATE_SLUGS, INDUSTRY_TEMPLATE_SLUGS
from app.studio.registry import (
    BUILD_PHASE_LABELS,
    BUILD_PHASE_ORDER,
    TEMPLATE_REGISTRY,
    RegistryEntry,
    resolve_alias,
)
from app.studio.schemas import (
    BlueprintWarning,
    BuildPlanStep,
    BuildPlanSummary,
    ComposedModule,
    DependencyEdge,
    ModuleKind,
    ProductBlueprint,
    StudioComposeResult,
)


def _truthy_dict_flag(obj: Dict[str, Any], *keys: str) -> bool:
    for key in keys:
        val = obj.get(key)
        if val is True:
            return True
        if isinstance(val, (list, dict)) and val:
            return True
        if isinstance(val, str) and val.strip():
            return True
    return False


def _lower_set(items: List[str]) -> Set[str]:
    return {str(x).strip().lower() for x in items if str(x).strip()}


def _pick_marketplace_slug(
    entry: RegistryEntry,
    blueprint: ProductBlueprint,
    recommendations: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    recs = recommendations or {}
    preferred: List[str] = []
    preferred.extend(list(entry.marketplace_templates))
    preferred.extend([str(t) for t in (recs.get("templates") or []) if t])
    industry = (blueprint.industry or "").lower()
    category = (blueprint.marketplace_category or blueprint.product_type or "saas").lower()
    preferred.extend(INDUSTRY_TEMPLATE_SLUGS.get(industry, []))
    preferred.extend(CATEGORY_TEMPLATE_SLUGS.get(category, []))
    for slug in preferred:
        if slug and slug in entry.marketplace_templates:
            return slug
    if entry.marketplace_templates:
        return entry.marketplace_templates[0]
    for slug in preferred:
        if slug:
            return str(slug)
    return None


def detect_required_keys(
    blueprint: ProductBlueprint,
    *,
    recommendations: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Return registry_key → detection reason."""
    pages = _lower_set(blueprint.pages)
    modules = _lower_set(blueprint.backend_modules)
    integrations = _lower_set(blueprint.integrations)
    roles = _lower_set(blueprint.roles)
    workflows = _lower_set(blueprint.workflows)
    ai = _lower_set(blueprint.ai_features)
    auth = blueprint.authentication or {}
    billing = blueprint.billing or {}
    payments = blueprint.payments or {}
    knowledge = blueprint.knowledge or {}
    product_type = (blueprint.product_type or "").lower()
    detected: Dict[str, str] = {}

    def mark(key: str, reason: str) -> None:
        if key not in detected:
            detected[key] = reason

    # Foundation — almost always for SaaS-like products
    saas_like = product_type in {"saas", "crm", "marketplace", "helpdesk", "ecommerce"}
    if (
        auth
        or "auth" in modules
        or "authentication" in modules
        or any(p in pages for p in ("login", "signup", "register"))
        or saas_like
        or blueprint.roles
    ):
        mark("authentication", "Auth / users / login implied")
        mark("rbac", "Roles or multi-user app implied")
    if blueprint.database_tables or saas_like or "database" in modules:
        mark("database", "Database tables or SaaS data model")
    if "storage" in modules or "storage" in integrations or knowledge.get("enabled"):
        mark("storage", "Uploads/documents/knowledge storage")
    if (
        "notifications" in modules
        or "email" in integrations
        or "sms" in integrations
        or any("notif" in w for w in workflows)
    ):
        mark("notifications", "Email/SMS/notifications required")

    # Commerce
    if (
        billing.get("enabled")
        or "billing" in modules
        or "payments" in modules
        or "subscription" in " ".join(workflows)
        or saas_like
    ):
        mark("billing", "Billing/plans/subscriptions implied")
    if (
        payments.get("providers")
        or "payments" in modules
        or "stripe" in integrations
        or "razorpay" in integrations
        or "billing" in detected
    ):
        mark("payments", "Payment providers or billing enabled")

    # Surfaces
    if any("admin" in p for p in pages) or "admin" in roles or "company_owner" in roles:
        mark("admin", "Admin page or owner/admin role")
    if (
        any("dashboard" in p for p in pages)
        or blueprint.dashboard_modules
        or saas_like
        or "admin" in detected
    ):
        mark("dashboard", "Dashboard / app shell required")
    if (
        any("landing" in p for p in pages)
        or product_type in {"website", "landing"}
        or any("website" in p for p in pages)
    ):
        mark("landing_page", "Landing / marketing site required")

    # AI stack
    if ai or "ai gateway" in modules or "agents" in modules or "ai" in modules:
        mark("ai_agent", "AI features / Agents / AI Gateway")
    if (
        knowledge.get("enabled")
        or knowledge.get("rag")
        or "knowledge" in modules
        or "rag" in ai
        or "memory" in ai
    ):
        mark("knowledge", "Knowledge / RAG required")
        mark("storage", "Knowledge packs need Storage")
    if "widget" in integrations or "widget" in modules or "embed" in integrations:
        mark("widget", "Embeddable widget requested")
    if ai and ("chat" in ai or "appointment_assistant" in ai):
        mark("widget", "Chat/assistant benefits from Widget")
    if "ai_agent" in detected:
        mark("publisher", "Agents reuse Publisher for packaging")
        mark("marketplace", "Agents/templates distributed via Marketplace")

    # Marketplace / analytics
    recs = recommendations or {}
    if recs.get("templates") or recs.get("marketplace_assets") or "marketplace" in modules:
        mark("marketplace", "Marketplace templates recommended")
    if "analytics" in modules or "usage" in modules or "monitoring" in str(blueprint.deployment).lower():
        mark("analytics", "Analytics / monitoring implied")

    # Alias pass over free-form backend_modules / pages
    for raw in list(blueprint.backend_modules) + list(blueprint.pages):
        key = resolve_alias(raw)
        if key:
            mark(key, f"Mapped from blueprint item “{raw}”")

    # Ensure dependency closure for selected keys
    changed = True
    while changed:
        changed = False
        for key in list(detected.keys()):
            entry = TEMPLATE_REGISTRY.get(key)
            if not entry:
                continue
            for dep in entry.depends_on:
                if dep not in detected:
                    detected[dep] = f"Required by {entry.label}"
                    changed = True

    return detected


def _custom_candidates(blueprint: ProductBlueprint, mapped_keys: Set[str]) -> List[Tuple[str, str]]:
    """Domain-specific modules that are not in the platform registry."""
    customs: List[Tuple[str, str]] = []
    skip_tokens = {
        "api",
        "jobs",
        "users",
        "invoices",
        "plans",
        "webhooks",
        "domains",
        "ssl",
        "deployment",
        "docker",
        "compose",
        "website",
        "frontend",
        "backend",
    }
    for raw in blueprint.backend_modules:
        key = resolve_alias(raw)
        if key and key in mapped_keys:
            continue
        low = raw.strip().lower()
        if not low or low in skip_tokens:
            continue
        if any(tok in low for tok in skip_tokens) and resolve_alias(raw):
            continue
        if key:
            continue
        # Industry domain modules (appointments, patients, leads, …)
        customs.append((raw.strip(), f"No existing platform module for “{raw.strip()}”"))
    return customs


def compose_modules(
    blueprint: ProductBlueprint,
    *,
    recommendations: Optional[Dict[str, Any]] = None,
) -> List[ComposedModule]:
    detected = detect_required_keys(blueprint, recommendations=recommendations)
    modules: List[ComposedModule] = []

    for key in BUILD_PHASE_ORDER:
        if key not in detected:
            continue
        entry = TEMPLATE_REGISTRY[key]
        marketplace_slug = _pick_marketplace_slug(entry, blueprint, recommendations)
        if entry.marketplace_templates and marketplace_slug:
            kind = ModuleKind.MARKETPLACE
        else:
            kind = ModuleKind.EXISTING
        modules.append(
            ComposedModule(
                key=entry.key,
                label=entry.label,
                kind=kind,
                platform_ref=entry.platform_ref,
                marketplace_template=marketplace_slug if kind == ModuleKind.MARKETPLACE else None,
                depends_on=list(entry.depends_on),
                reason=detected[key],
                custom_effort="none",
                category=entry.category,
            )
        )

    mapped = {m.key for m in modules}
    for name, reason in _custom_candidates(blueprint, mapped):
        slug = name.lower().replace(" ", "_")[:64]
        modules.append(
            ComposedModule(
                key=f"custom:{slug}",
                label=name,
                kind=ModuleKind.CUSTOM,
                platform_ref=None,
                marketplace_template=None,
                depends_on=["database", "authentication"] if "authentication" in mapped else ["database"],
                reason=reason,
                custom_effort="medium",
                category="custom",
            )
        )
    return modules


def build_dependency_graph(modules: List[ComposedModule]) -> List[DependencyEdge]:
    keys = {m.key for m in modules}
    edges: List[DependencyEdge] = []
    for mod in modules:
        deps = [d for d in mod.depends_on if d in keys or d in TEMPLATE_REGISTRY]
        # Keep only edges to selected modules (or their registry keys if selected)
        deps = [d for d in deps if d in keys]
        edges.append(DependencyEdge(key=mod.key, label=mod.label, depends_on=deps))
    return edges


def build_dependency_tree(modules: List[ComposedModule]) -> List[Dict[str, Any]]:
    """Nested tree for UI — roots first."""
    by_key = {m.key: m for m in modules}
    children: Dict[str, List[str]] = {m.key: [] for m in modules}
    roots: List[str] = []
    for m in modules:
        live_deps = [d for d in m.depends_on if d in by_key]
        if not live_deps:
            roots.append(m.key)
        for d in live_deps:
            children[d].append(m.key)

    seen: Set[str] = set()

    def node(key: str) -> Dict[str, Any]:
        mod = by_key[key]
        kids = []
        for child in children.get(key, []):
            if child in seen:
                continue
            seen.add(child)
            kids.append(node(child))
        return {
            "key": mod.key,
            "label": mod.label,
            "kind": mod.kind.value if hasattr(mod.kind, "value") else mod.kind,
            "children": kids,
        }

    tree: List[Dict[str, Any]] = []
    for r in roots:
        if r in seen:
            continue
        seen.add(r)
        tree.append(node(r))
    # Orphans already processed via roots; include any leftover
    for m in modules:
        if m.key not in seen:
            seen.add(m.key)
            tree.append(node(m.key))
    return tree


def order_build_plan(modules: List[ComposedModule]) -> List[BuildPlanStep]:
    """Topological order with BUILD_PHASE_ORDER as tie-breaker (Auth → … → Website)."""
    by_key = {m.key: m for m in modules}
    phase_rank = {k: i for i, k in enumerate(BUILD_PHASE_ORDER)}
    pending = set(by_key.keys())
    ordered: List[str] = []

    while pending:
        ready = [
            k
            for k in pending
            if all(d not in pending for d in by_key[k].depends_on if d in by_key)
        ]
        if not ready:
            ready = list(pending)
        ready.sort(key=lambda k: (phase_rank.get(k, 10_000), k))
        pick = ready[0]
        ordered.append(pick)
        pending.remove(pick)

    steps: List[BuildPlanStep] = []
    for idx, key in enumerate(ordered, start=1):
        mod = by_key[key]
        phase = BUILD_PHASE_LABELS.get(key, "Custom" if key.startswith("custom:") else mod.label)
        steps.append(
            BuildPlanStep(
                order=idx,
                key=mod.key,
                label=mod.label,
                phase=phase,
                kind=mod.kind,
                depends_on=[d for d in mod.depends_on if d in by_key],
                platform_ref=mod.platform_ref,
                marketplace_template=mod.marketplace_template,
            )
        )
    # Planning marker only — Phase 3 does not deploy
    steps.append(
        BuildPlanStep(
            order=len(steps) + 1,
            key="deployment",
            label="Deployment",
            phase="Deployment",
            kind=ModuleKind.EXISTING,
            depends_on=[s.key for s in steps if not s.key.startswith("custom:")][-3:]
            if steps
            else [],
            platform_ref="deploy",
            marketplace_template=None,
            note="Planning marker only — Phase 3 does not deploy",
        )
    )
    return steps


def summarize_plan(
    modules: List[ComposedModule],
    *,
    blueprint: ProductBlueprint,
) -> BuildPlanSummary:
    existing = sum(1 for m in modules if m.kind == ModuleKind.EXISTING)
    marketplace = sum(1 for m in modules if m.kind == ModuleKind.MARKETPLACE)
    custom = sum(1 for m in modules if m.kind == ModuleKind.CUSTOM)
    total = max(len(modules), 1)
    reuse = round(100.0 * (existing + marketplace) / total, 1)

    if custom == 0:
        custom_work = "none"
    elif custom <= 2 and (blueprint.estimated_complexity or "").lower() != "high":
        custom_work = "low"
    elif custom <= 4:
        custom_work = "medium"
    else:
        custom_work = "high"

    warnings: List[BlueprintWarning] = []
    if custom:
        warnings.append(
            BlueprintWarning(
                code="custom_modules_required",
                severity="warn",
                message=f"{custom} custom module(s) needed — prefer existing platform modules when possible.",
                field="modules",
            )
        )
    if reuse < 70:
        warnings.append(
            BlueprintWarning(
                code="low_reuse",
                severity="warn",
                message=f"Reuse is {reuse}% — review custom mappings before codegen phases.",
                field="reuse_percent",
            )
        )
    if not any(m.key == "authentication" for m in modules):
        warnings.append(
            BlueprintWarning(
                code="compose_missing_auth",
                severity="error",
                message="Compose plan missing Authentication — unexpected for SaaS products.",
                field="authentication",
            )
        )
    if any(m.key == "ai_agent" for m in modules) and not any(m.key == "knowledge" for m in modules):
        warnings.append(
            BlueprintWarning(
                code="ai_without_knowledge",
                severity="info",
                message="AI Agent without Knowledge — consider RAG packs for grounded answers.",
                field="knowledge",
            )
        )
    return BuildPlanSummary(
        reuse_percent=reuse,
        existing_count=existing,
        marketplace_count=marketplace,
        custom_count=custom,
        module_count=len(modules),
        estimated_custom_work=custom_work,
        warnings=warnings,
    )


def compose_blueprint(
    blueprint: ProductBlueprint,
    *,
    recommendations: Optional[Dict[str, Any]] = None,
) -> StudioComposeResult:
    """Full Module Composer pipeline — pure, no I/O."""
    modules = compose_modules(blueprint, recommendations=recommendations)
    graph = build_dependency_graph(modules)
    tree = build_dependency_tree(modules)
    plan = order_build_plan(modules)
    summary = summarize_plan(modules, blueprint=blueprint)
    return StudioComposeResult(
        modules=modules,
        dependency_graph=graph,
        dependency_tree=tree,
        build_plan=plan,
        summary=summary,
    )
