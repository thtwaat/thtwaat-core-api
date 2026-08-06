"""Studio Review Center — aggregate manifests, validate, estimate, export (no codegen/deploy)."""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Sequence

from app.monitoring.exports import _simple_pdf
from app.studio.schemas import (
    AiManifest,
    BackendManifest,
    BlueprintWarning,
    BuildEstimate,
    ComposedModule,
    DependencyEdge,
    FrontendManifest,
    InfraManifest,
    ProductBlueprint,
    RequiredSecretGroup,
    ReviewArchitecture,
    ReviewArtifactStatus,
    ReviewManifest,
    ReviewValidationIssue,
)


SECRET_CATALOG: Sequence[tuple[str, str, tuple[str, ...]]] = (
    ("openai", "OpenAI", ("OPENAI_API_KEY",)),
    ("gemini", "Gemini", ("GEMINI_API_KEY",)),
    ("anthropic", "Anthropic", ("ANTHROPIC_API_KEY",)),
    ("openrouter", "OpenRouter", ("OPENROUTER_API_KEY",)),
    ("stripe", "Stripe", ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")),
    ("razorpay", "Razorpay", ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET")),
    ("smtp", "SMTP", ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")),
    ("storage", "Storage", ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET")),
    ("analytics", "Analytics", ("METRICS_TOKEN", "PROMETHEUS_URL", "GRAFANA_URL")),
)


def _module_keys(modules: List[ComposedModule]) -> set[str]:
    return {m.key for m in modules}


def build_architecture(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
    backend: Optional[BackendManifest],
    ai: Optional[AiManifest],
    infra: Optional[InfraManifest],
    dependency_graph: List[DependencyEdge],
) -> ReviewArchitecture:
    pages = list(frontend.pages) if frontend and frontend.pages else []
    page_names = (
        [getattr(p, "title", None) or getattr(p, "id", str(p)) for p in pages]
        if pages
        else list(blueprint.pages or [])
    )
    routes: List[str] = []
    if frontend:
        for r in frontend.routes or []:
            if getattr(r, "path", None):
                routes.append(str(r.path))
        for nav in frontend.nav or []:
            if getattr(nav, "route", None):
                routes.append(str(nav.route))
        for p in frontend.pages or []:
            if getattr(p, "route", None):
                routes.append(str(p.route))
    routes = list(dict.fromkeys(routes))

    tables: List[str] = []
    if backend and backend.database and backend.database.tables:
        tables = [t.name for t in backend.database.tables]
    else:
        tables = list(blueprint.database_tables or [])

    apis: List[str] = []
    if backend and backend.api and backend.api.endpoints:
        apis = [f"{ep.method} {ep.path}" for ep in backend.api.endpoints]
    providers = [p.provider for p in (ai.providers if ai else [])]
    knowledge = {}
    if ai and ai.knowledge:
        knowledge = dict(ai.knowledge)
    elif blueprint.knowledge:
        knowledge = dict(blueprint.knowledge)

    roles: List[str] = []
    if backend and backend.rbac and backend.rbac.roles:
        roles = list(backend.rbac.roles)
    else:
        roles = list(blueprint.roles or [])

    targets: List[str] = []
    if infra and infra.targets:
        targets = [t.id for t in infra.targets if t.recommended] or [t.id for t in infra.targets[:3]]
    else:
        targets = [str(t) for t in (blueprint.deployment or {}).get("targets") or []]

    deps = [
        {"key": e.key, "label": e.label, "depends_on": list(e.depends_on or [])}
        for e in dependency_graph
    ]
    return ReviewArchitecture(
        pages=page_names,
        routes=routes,
        database=tables,
        api=apis,
        ai_providers=providers,
        knowledge=knowledge,
        rbac=roles,
        deployment_targets=targets,
        dependency_graph=deps,
        modules=[{"key": m.key, "label": m.label, "kind": str(m.kind)} for m in modules],
    )


def validate_review(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
    backend: Optional[BackendManifest],
    ai: Optional[AiManifest],
    infra: Optional[InfraManifest],
) -> List[ReviewValidationIssue]:
    issues: List[ReviewValidationIssue] = []
    keys = _module_keys(modules)
    deploy = blueprint.deployment or {}
    billing = blueprint.billing or {}
    payments = blueprint.payments or {}

    if not frontend:
        issues.append(
            ReviewValidationIssue(
                code="missing_frontend",
                severity="error",
                message="Frontend manifest missing — run Generate Frontend",
                field="frontend",
            )
        )
    if not backend:
        issues.append(
            ReviewValidationIssue(
                code="missing_backend",
                severity="error",
                message="Backend manifest missing — run Generate Backend",
                field="backend",
            )
        )
    if not ai:
        issues.append(
            ReviewValidationIssue(
                code="missing_ai",
                severity="error",
                message="AI manifest missing — run Generate AI",
                field="ai",
            )
        )
    if not infra:
        issues.append(
            ReviewValidationIssue(
                code="missing_infrastructure",
                severity="error",
                message="Infrastructure manifest missing — run Generate Infrastructure",
                field="infrastructure",
            )
        )

    # Missing AI provider
    providers = {p.provider for p in (ai.providers if ai else [])}
    primary = next((p for p in (ai.providers if ai else []) if p.recommended_primary), None)
    if "ai_agent" in keys or (blueprint.ai_features or []):
        if not providers:
            issues.append(
                ReviewValidationIssue(
                    code="missing_ai_provider",
                    severity="error",
                    message="AI features planned but no AI provider selected",
                    field="ai_providers",
                )
            )
        elif primary and primary.provider != "ollama":
            issues.append(
                ReviewValidationIssue(
                    code="missing_api_keys",
                    severity="warn",
                    message=f"API key required before go-live for provider '{primary.provider}'",
                    field="api_keys",
                )
            )

    # Billing
    if "billing" in keys or billing.get("enabled") or payments.get("providers"):
        pay_providers = payments.get("providers") or []
        if not pay_providers and not (infra and any(e.group == "payments" for e in infra.environment)):
            issues.append(
                ReviewValidationIssue(
                    code="missing_billing",
                    severity="warn",
                    message="Billing module planned but no payment provider configured",
                    field="billing",
                )
            )

    # Storage
    if "storage" in keys or "knowledge" in keys or (blueprint.knowledge or {}).get("enabled"):
        storage_ok = False
        if infra:
            storage_ok = any(c.id == "storage" for c in infra.components) or any(
                e.group == "storage" for e in infra.environment
            )
        if backend and backend.storage:
            storage_ok = True
        if not storage_ok:
            issues.append(
                ReviewValidationIssue(
                    code="missing_storage",
                    severity="warn",
                    message="Storage/knowledge planned but storage not present in backend/infra",
                    field="storage",
                )
            )

    # Domain / public URL
    domain = deploy.get("domain") or deploy.get("public_domain") or deploy.get("hostname")
    env_has_url = False
    if infra:
        env_has_url = any(e.key == "PUBLIC_API_BASE_URL" for e in infra.environment)
    if not domain and not env_has_url:
        issues.append(
            ReviewValidationIssue(
                code="missing_domain",
                severity="warn",
                message="No domain / PUBLIC_API_BASE_URL planned — set before deploy",
                field="domain",
            )
        )
    elif not domain:
        issues.append(
            ReviewValidationIssue(
                code="missing_domain",
                severity="info",
                message="Confirm PUBLIC_API_BASE_URL and CORS_ORIGINS for production domain",
                field="domain",
            )
        )

    # Deployment target
    targets = list(deploy.get("targets") or [])
    if infra and infra.targets:
        targets = targets or [t.id for t in infra.targets if t.recommended]
    if not targets:
        issues.append(
            ReviewValidationIssue(
                code="missing_deployment_target",
                severity="error",
                message="No deployment target selected (docker/vps/…)",
                field="deployment",
            )
        )

    # Secrets
    if infra:
        required_secrets = [
            e.key for e in infra.environment if e.required and e.secret
        ] or list((infra.secrets or {}).get("required") or [])
        if required_secrets:
            issues.append(
                ReviewValidationIssue(
                    code="missing_secrets",
                    severity="warn",
                    message=f"Required secrets before go-live: {', '.join(required_secrets[:8])}",
                    field="secrets",
                )
            )
    else:
        issues.append(
            ReviewValidationIssue(
                code="missing_secrets",
                severity="warn",
                message="Cannot list secrets until Infrastructure is generated",
                field="secrets",
            )
        )

    # Email
    integrations = {str(i).lower() for i in (blueprint.integrations or [])}
    if "email" in integrations or "smtp" in integrations:
        has_smtp = False
        if infra:
            has_smtp = any(e.group == "email" or e.key.startswith("SMTP_") for e in infra.environment)
        if not has_smtp:
            issues.append(
                ReviewValidationIssue(
                    code="missing_email_provider",
                    severity="warn",
                    message="Email integration planned but SMTP env not listed",
                    field="email",
                )
            )

    return issues


def list_required_secrets(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    ai: Optional[AiManifest],
    infra: Optional[InfraManifest],
) -> List[RequiredSecretGroup]:
    keys = _module_keys(modules)
    providers = {p.provider for p in (ai.providers if ai else [])}
    payments = {
        str(p).lower() for p in ((blueprint.payments or {}).get("providers") or [])
    }
    integrations = {str(i).lower() for i in (blueprint.integrations or [])}
    groups: List[RequiredSecretGroup] = []

    for gid, label, env_keys in SECRET_CATALOG:
        required = False
        reason = ""
        if gid in {"openai", "gemini", "anthropic", "openrouter"}:
            if gid in providers:
                required = gid != "ollama"
                reason = f"AI provider '{gid}' selected"
            elif "ai_agent" in keys and gid == "openai" and not providers:
                required = True
                reason = "Default AI provider when none selected"
        elif gid == "stripe":
            required = "stripe" in payments or ("billing" in keys and not payments)
            reason = "Billing / Stripe"
        elif gid == "razorpay":
            required = "razorpay" in payments
            reason = "Billing / Razorpay"
        elif gid == "smtp":
            required = "email" in integrations or "smtp" in integrations
            reason = "Email integration"
        elif gid == "storage":
            # Local default needs no cloud keys; list as optional advisory
            if "storage" in keys or "knowledge" in keys or (blueprint.knowledge or {}).get("enabled"):
                groups.append(
                    RequiredSecretGroup(
                        id=gid,
                        label=label,
                        keys=list(env_keys),
                        required=False,
                        reason="Needed only if STORAGE_PROVIDER is s3/cloud",
                    )
                )
            continue
        elif gid == "analytics":
            required = False
            reason = "Optional monitoring/metrics"
        groups.append(
            RequiredSecretGroup(
                id=gid,
                label=label,
                keys=list(env_keys),
                required=required,
                reason=reason or ("Optional" if not required else ""),
            )
        )
    return groups


def estimate_build(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
    backend: Optional[BackendManifest],
    ai: Optional[AiManifest],
    infra: Optional[InfraManifest],
) -> BuildEstimate:
    complexity = (blueprint.estimated_complexity or "medium").lower()
    build_time = blueprint.estimated_build_time or {
        "low": "1-2 weeks",
        "medium": "2-4 weeks",
        "high": "4-8 weeks",
    }.get(complexity, "2-4 weeks")

    page_count = (
        frontend.summary.page_count
        if frontend and frontend.summary
        else len(blueprint.pages or [])
    )
    table_count = (
        backend.summary.table_count
        if backend and backend.summary
        else len(blueprint.database_tables or [])
    )
    api_count = (
        backend.summary.endpoint_count
        if backend and backend.summary
        else 0
    )
    queue_count = (
        backend.summary.queue_count if backend and backend.summary else 0
    )
    worker_count = 1 if queue_count or any(m.key in {"ai_agent", "billing"} for m in modules) else 0
    if infra and any(c.id == "workers" for c in infra.components):
        worker_count = max(worker_count, 1)
    job_count = queue_count + (1 if infra and any(c.id == "scheduler" for c in infra.components) else 0)

    # Generated files estimate (planning only — not emitting)
    generated_files = page_count * 2 + table_count + api_count + len(modules) * 2
    custom_modules = sum(1 for m in modules if str(m.kind) == "custom_module" or getattr(m.kind, "value", "") == "custom_module")
    generated_files += custom_modules * 5

    ai_cost = float(ai.cost.estimated_monthly_usd if ai and ai.cost else 0.0)
    infra_cost = float(infra.cost.monthly_total_usd if infra and infra.cost else 0.0)
    # One-time build effort heuristic (not platform billing)
    effort_usd = {"low": 800.0, "medium": 2500.0, "high": 6000.0}.get(complexity, 2500.0)
    effort_usd += custom_modules * 400.0

    return BuildEstimate(
        estimated_build_time=build_time,
        estimated_cost_usd=round(effort_usd, 2),
        complexity=complexity,
        generated_files=generated_files,
        database_tables=table_count,
        rest_apis=api_count,
        workers=worker_count,
        background_jobs=job_count,
        ai_cost_monthly_usd=round(ai_cost, 2),
        infrastructure_cost_monthly_usd=round(infra_cost, 2),
        monthly_run_cost_usd=round(ai_cost + (infra.cost.infrastructure_usd + infra.cost.storage_usd + infra.cost.bandwidth_usd if infra and infra.cost else infra_cost), 2)
        if infra
        else round(ai_cost, 2),
        notes=[
            "Estimates are planning-only — Phase 8 does not generate source or deploy",
            "Generated files count is a preview of future codegen scope",
            f"Modules: {len(modules)} ({custom_modules} custom)",
        ],
    )


def artifact_statuses(
    *,
    blueprint_version: Optional[int],
    build_plan_version: Optional[int],
    frontend_version: Optional[int],
    frontend_status: Optional[str],
    backend_version: Optional[int],
    backend_status: Optional[str],
    ai_version: Optional[int],
    ai_status: Optional[str],
    infra_version: Optional[int],
    infra_status: Optional[str],
) -> List[ReviewArtifactStatus]:
    return [
        ReviewArtifactStatus(
            id="blueprint",
            label="Blueprint",
            present=blueprint_version is not None,
            version=blueprint_version,
            status="ready" if blueprint_version else "missing",
        ),
        ReviewArtifactStatus(
            id="build_plan",
            label="Build Plan",
            present=build_plan_version is not None,
            version=build_plan_version,
            status="ready" if build_plan_version else "missing",
        ),
        ReviewArtifactStatus(
            id="frontend",
            label="Frontend",
            present=frontend_version is not None,
            version=frontend_version,
            status=frontend_status or ("missing" if frontend_version is None else "draft"),
        ),
        ReviewArtifactStatus(
            id="backend",
            label="Backend",
            present=backend_version is not None,
            version=backend_version,
            status=backend_status or ("missing" if backend_version is None else "draft"),
        ),
        ReviewArtifactStatus(
            id="ai",
            label="AI",
            present=ai_version is not None,
            version=ai_version,
            status=ai_status or ("missing" if ai_version is None else "draft"),
        ),
        ReviewArtifactStatus(
            id="infrastructure",
            label="Infrastructure",
            present=infra_version is not None,
            version=infra_version,
            status=infra_status or ("missing" if infra_version is None else "draft"),
        ),
    ]


def build_review_manifest(
    *,
    project_title: str,
    project_status: str,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    dependency_graph: List[DependencyEdge],
    frontend: Optional[FrontendManifest],
    backend: Optional[BackendManifest],
    ai: Optional[AiManifest],
    infra: Optional[InfraManifest],
    blueprint_version: Optional[int],
    build_plan_version: Optional[int],
    frontend_version: Optional[int] = None,
    frontend_status: Optional[str] = None,
    backend_version: Optional[int] = None,
    backend_status: Optional[str] = None,
    ai_version: Optional[int] = None,
    ai_status: Optional[str] = None,
    infra_version: Optional[int] = None,
    infra_status: Optional[str] = None,
) -> ReviewManifest:
    architecture = build_architecture(
        blueprint=blueprint,
        modules=modules,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
        dependency_graph=dependency_graph,
    )
    issues = validate_review(
        blueprint=blueprint,
        modules=modules,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
    )
    secrets = list_required_secrets(
        blueprint=blueprint, modules=modules, ai=ai, infra=infra
    )
    estimate = estimate_build(
        blueprint=blueprint,
        modules=modules,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
    )
    artifacts = artifact_statuses(
        blueprint_version=blueprint_version,
        build_plan_version=build_plan_version,
        frontend_version=frontend_version,
        frontend_status=frontend_status,
        backend_version=backend_version,
        backend_status=backend_status,
        ai_version=ai_version,
        ai_status=ai_status,
        infra_version=infra_version,
        infra_status=infra_status,
    )
    blocking = [i for i in issues if i.severity == "error"]
    ready = (
        all(a.present for a in artifacts)
        and len(blocking) == 0
        and frontend is not None
        and backend is not None
        and ai is not None
        and infra is not None
    )
    warnings = [
        BlueprintWarning(code=i.code, severity=i.severity, message=i.message, field=i.field)
        for i in issues
    ]
    return ReviewManifest(
        schema_version=1,
        product_name=project_title,
        project_status=project_status,
        industry=blueprint.industry,
        product_type=blueprint.product_type,
        ready_to_approve=ready,
        artifacts=artifacts,
        architecture=architecture,
        validation=issues,
        estimate=estimate,
        required_secrets=secrets,
        summaries={
            "blueprint": {
                "pages": len(blueprint.pages or []),
                "tables": len(blueprint.database_tables or []),
                "complexity": blueprint.estimated_complexity,
                "build_time": blueprint.estimated_build_time,
            },
            "frontend": frontend.summary.model_dump(mode="json") if frontend and frontend.summary else {},
            "backend": backend.summary.model_dump(mode="json") if backend and backend.summary else {},
            "ai": ai.summary.model_dump(mode="json") if ai and ai.summary else {},
            "infrastructure": infra.summary.model_dump(mode="json")
            if infra and infra.summary
            else {},
        },
        versions={
            "blueprint": blueprint_version,
            "build_plan": build_plan_version,
            "frontend": frontend_version,
            "backend": backend_version,
            "ai": ai_version,
            "infrastructure": infra_version,
        },
        warnings=warnings,
        note="Review Center only — no source generation and no deployment",
    )


def review_to_markdown(review: ReviewManifest) -> str:
    lines = [
        f"# THTWAAT Studio Review — {review.product_name}",
        "",
        f"**Status:** {review.project_status}  ",
        f"**Ready to approve:** {'yes' if review.ready_to_approve else 'no'}  ",
        f"**Industry:** {review.industry} · **Type:** {review.product_type}",
        "",
        "## Artifacts",
        "",
    ]
    for a in review.artifacts:
        mark = "✓" if a.present else "✗"
        lines.append(f"- {mark} **{a.label}** v{a.version or '—'} ({a.status})")
    lines += ["", "## Architecture", ""]
    arch = review.architecture
    lines.append(f"- **Pages:** {', '.join(arch.pages) or '—'}")
    lines.append(f"- **Routes:** {', '.join(arch.routes) or '—'}")
    lines.append(f"- **Database:** {', '.join(arch.database) or '—'}")
    lines.append(f"- **API count:** {len(arch.api)}")
    lines.append(f"- **AI providers:** {', '.join(arch.ai_providers) or '—'}")
    lines.append(f"- **RBAC roles:** {', '.join(arch.rbac) or '—'}")
    lines.append(f"- **Deployment targets:** {', '.join(arch.deployment_targets) or '—'}")
    lines += ["", "### Dependency graph", ""]
    for edge in arch.dependency_graph:
        deps = ", ".join(edge.get("depends_on") or []) or "root"
        lines.append(f"- {edge.get('label') or edge.get('key')} ← {deps}")
    lines += ["", "## Validation", ""]
    if not review.validation:
        lines.append("- No issues")
    else:
        for issue in review.validation:
            lines.append(f"- **[{issue.severity}]** {issue.message} (`{issue.code}`)")
    est = review.estimate
    lines += [
        "",
        "## Build estimate",
        "",
        f"- Build time: {est.estimated_build_time}",
        f"- Complexity: {est.complexity}",
        f"- Estimated build cost: ${est.estimated_cost_usd}",
        f"- Generated files (plan): {est.generated_files}",
        f"- Database tables: {est.database_tables}",
        f"- REST APIs: {est.rest_apis}",
        f"- Workers: {est.workers}",
        f"- Background jobs: {est.background_jobs}",
        f"- AI cost / mo: ${est.ai_cost_monthly_usd}",
        f"- Infra cost / mo: ${est.infrastructure_cost_monthly_usd}",
        "",
        "## Required secrets",
        "",
    ]
    for g in review.required_secrets:
        flag = "REQUIRED" if g.required else "optional"
        lines.append(f"- **{g.label}** ({flag}): {', '.join(g.keys)}")
    lines += ["", f"_{review.note}_", ""]
    return "\n".join(lines)


def review_to_pdf_bytes(review: ReviewManifest) -> bytes:
    md = review_to_markdown(review)
    # PDF helper is text-oriented; keep ASCII-ish
    text = md.replace("✓", "[x]").replace("✗", "[ ]").replace("·", "-")
    return _simple_pdf(text[:12000])


def export_review_payload(
    *,
    review: ReviewManifest,
    kind: str,
    format: str,
    blueprint: Optional[ProductBlueprint] = None,
    build_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fmt = (format or "json").lower().strip()
    export_kind = (kind or "review").lower().strip()
    if export_kind not in {"review", "blueprint", "build_plan"}:
        raise ValueError("kind must be review, blueprint, or build_plan")
    if fmt not in {"json", "markdown", "md", "pdf"}:
        raise ValueError("format must be json, markdown, or pdf")
    if fmt == "md":
        fmt = "markdown"

    if export_kind == "blueprint":
        if not blueprint:
            raise ValueError("Blueprint not available")
        data: Any = blueprint.model_dump(mode="json")
        title = f"{review.product_name}-blueprint"
        md = (
            f"# Blueprint — {review.product_name}\n\n```json\n"
            + json.dumps(data, indent=2)
            + "\n```\n"
        )
    elif export_kind == "build_plan":
        if not build_plan:
            raise ValueError("Build plan not available")
        data = build_plan
        title = f"{review.product_name}-build-plan"
        md = (
            f"# Build Plan — {review.product_name}\n\n```json\n"
            + json.dumps(data, indent=2)
            + "\n```\n"
        )
    else:
        data = review.model_dump(mode="json")
        title = f"{review.product_name}-review"
        md = review_to_markdown(review)

    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in title.lower()).strip("-")[
        :64
    ] or "studio-export"

    if fmt == "json":
        return {
            "kind": export_kind,
            "format": "json",
            "filename": f"{slug}.json",
            "content_type": "application/json",
            "encoding": "utf-8",
            "content": json.dumps(data, indent=2),
        }
    if fmt == "markdown":
        return {
            "kind": export_kind,
            "format": "markdown",
            "filename": f"{slug}.md",
            "content_type": "text/markdown; charset=utf-8",
            "encoding": "utf-8",
            "content": md,
        }
    # pdf
    if export_kind == "review":
        raw = review_to_pdf_bytes(review)
    else:
        raw = _simple_pdf(md[:12000])
    return {
        "kind": export_kind,
        "format": "pdf",
        "filename": f"{slug}.pdf",
        "content_type": "application/pdf",
        "encoding": "base64",
        "content": base64.b64encode(raw).decode("ascii"),
    }


def can_approve(review: ReviewManifest) -> tuple[bool, str]:
    if not review.ready_to_approve:
        missing = [a.label for a in review.artifacts if not a.present]
        errors = [i.message for i in review.validation if i.severity == "error"]
        parts = []
        if missing:
            parts.append("missing: " + ", ".join(missing))
        if errors:
            parts.append("; ".join(errors[:3]))
        return False, parts[0] if parts else "Review is not ready to approve"
    return True, ""
