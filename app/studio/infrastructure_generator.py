"""Studio Infrastructure Generator — backend + AI → infra plan (no codegen / no deploy)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.studio.schemas import (
    AiManifest,
    BackendManifest,
    BlueprintWarning,
    ComposedModule,
    InfraComponent,
    InfraCostEstimate,
    InfraEnvVar,
    InfraManifest,
    InfraSummary,
    InfraTarget,
    ProductBlueprint,
)


# Reuse existing THTWAAT production stack — never invent parallel runtimes
PLATFORM_INFRA = {
    "docker": "Dockerfile",
    "compose": "docker-compose.prod.yml",
    "nginx": "nginx/",
    "redis": "redis:7-alpine (compose)",
    "postgres": "pgvector/pgvector:pg15 (compose)",
    "workers": "thtwaat-worker (compose)",
    "scheduler": "thtwaat-scheduler (compose)",
    "monitoring": "app/monitoring + prometheus/grafana links",
    "billing": "app/payments",
    "ai_gateway": "app/ai + ollama service",
    "backups": "data/backups + backup service",
    "rate_limiting": "fastapi-limiter + redis",
    "storage": "app/storage + data/uploads",
}

DEPLOYMENT_TARGETS = (
    "docker",
    "vps",
    "coolify",
    "railway",
    "aws",
    "azure",
    "google_cloud",
    "digitalocean",
    "kubernetes",
)

OPTIONAL_SECRET_GROUPS = {
    "ai_providers": [
        ("OPENAI_API_KEY", "openai"),
        ("GEMINI_API_KEY", "gemini"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("OPENROUTER_API_KEY", "openrouter"),
    ],
    "payments": [
        ("STRIPE_SECRET_KEY", "stripe"),
        ("STRIPE_WEBHOOK_SECRET", "stripe"),
        ("RAZORPAY_KEY_ID", "razorpay"),
        ("RAZORPAY_KEY_SECRET", "razorpay"),
    ],
    "storage": [
        ("AWS_ACCESS_KEY_ID", "s3"),
        ("AWS_SECRET_ACCESS_KEY", "s3"),
        ("S3_BUCKET", "s3"),
    ],
    "email": [
        ("SMTP_HOST", "smtp"),
        ("SMTP_USERNAME", "smtp"),
        ("SMTP_PASSWORD", "smtp"),
        ("SMTP_FROM", "smtp"),
    ],
    "analytics": [
        ("METRICS_TOKEN", "metrics"),
        ("PROMETHEUS_URL", "metrics"),
        ("GRAFANA_URL", "metrics"),
    ],
}


def generate_components(
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    ai: Optional[AiManifest],
) -> List[InfraComponent]:
    module_keys = {m.key for m in modules}
    components = [
        InfraComponent(
            id="docker",
            name="Docker",
            category="runtime",
            reuse=True,
            platform_ref=PLATFORM_INFRA["docker"],
            details={"images": ["thtwaat-api", "thtwaat-web_app", "thtwaat-nginx"]},
        ),
        InfraComponent(
            id="compose",
            name="Docker Compose",
            category="runtime",
            reuse=True,
            platform_ref=PLATFORM_INFRA["compose"],
            details={"file": "docker-compose.prod.yml", "network": "thtwaat_net"},
        ),
        InfraComponent(
            id="nginx",
            name="Nginx",
            category="edge",
            reuse=True,
            platform_ref=PLATFORM_INFRA["nginx"],
            details={"ports": ["80", "443"], "tls": True, "acme": True},
        ),
        InfraComponent(
            id="postgres",
            name="Postgres",
            category="data",
            reuse=True,
            platform_ref=PLATFORM_INFRA["postgres"],
            details={"engine": "pgvector/pg15", "healthcheck": True},
        ),
        InfraComponent(
            id="redis",
            name="Redis",
            category="data",
            reuse=True,
            platform_ref=PLATFORM_INFRA["redis"],
            details={"uses": ["cache", "rate_limit", "queues"]},
        ),
        InfraComponent(
            id="workers",
            name="Workers",
            category="jobs",
            reuse=True,
            platform_ref=PLATFORM_INFRA["workers"],
            details={"queues": ["emails", "ai_jobs", "imports", "exports"]},
        ),
        InfraComponent(
            id="scheduler",
            name="Scheduler",
            category="jobs",
            reuse=True,
            platform_ref=PLATFORM_INFRA["scheduler"],
            details={"interval_env": "SCHEDULER_INTERVAL_SECONDS"},
        ),
        InfraComponent(
            id="healthchecks",
            name="Health Checks",
            category="ops",
            reuse=True,
            platform_ref="compose healthcheck blocks",
            details={"services": ["api", "web_app", "db", "redis", "nginx"]},
        ),
        InfraComponent(
            id="logging",
            name="Logging",
            category="ops",
            reuse=True,
            platform_ref="container stdout + app logging",
            details={"format": "structured", "retention": "host/log driver"},
        ),
        InfraComponent(
            id="monitoring",
            name="Monitoring",
            category="ops",
            reuse=True,
            platform_ref=PLATFORM_INFRA["monitoring"],
            details={"prometheus": True, "grafana": True},
        ),
        InfraComponent(
            id="metrics",
            name="Metrics",
            category="ops",
            reuse=True,
            platform_ref="app/monitoring + /metrics",
            details={"token_env": "METRICS_TOKEN"},
        ),
        InfraComponent(
            id="tracing",
            name="Tracing",
            category="ops",
            reuse=True,
            platform_ref="app/monitoring (plan)",
            details={"status": "plan", "note": "Extend existing monitoring — do not add parallel APM stack"},
        ),
        InfraComponent(
            id="backups",
            name="Backups",
            category="data",
            reuse=True,
            platform_ref=PLATFORM_INFRA["backups"],
            details={"path": "data/backups", "retention_env": "BACKUP_RETENTION_DAYS"},
        ),
        InfraComponent(
            id="restore",
            name="Restore Strategy",
            category="data",
            reuse=True,
            platform_ref="docs/ops + backup volume",
            details={
                "steps": ["stop writers", "restore pg dump", "verify alembic current", "smoke health"],
            },
        ),
        InfraComponent(
            id="scaling",
            name="Scaling Plan",
            category="ops",
            reuse=True,
            platform_ref="compose replicas / future k8s plan",
            details={
                "api": "horizontal via compose/k8s",
                "worker": "scale replicas",
                "db": "vertical first",
            },
        ),
        InfraComponent(
            id="rate_limiting",
            name="Rate Limiting",
            category="security",
            reuse=True,
            platform_ref=PLATFORM_INFRA["rate_limiting"],
            details={"backend": "redis", "middleware": "fastapi-limiter"},
        ),
        InfraComponent(
            id="cdn",
            name="CDN",
            category="edge",
            reuse=False,
            platform_ref=None,
            details={"status": "plan", "note": "Optional Cloudflare/edge in front of nginx"},
        ),
        InfraComponent(
            id="storage",
            name="Storage",
            category="data",
            reuse=True,
            platform_ref=PLATFORM_INFRA["storage"],
            details={"local": "data/uploads", "knowledge": "data/knowledge"},
        ),
        InfraComponent(
            id="env_secrets",
            name="Environment Variables / Secrets",
            category="security",
            reuse=True,
            platform_ref=".env.prod.example",
            details={"file": ".env.prod", "example": ".env.prod.example"},
        ),
    ]
    if "ai_agent" in module_keys or (ai and ai.agents):
        components.append(
            InfraComponent(
                id="ai_gateway_runtime",
                name="AI Gateway + Ollama",
                category="ai",
                reuse=True,
                platform_ref=PLATFORM_INFRA["ai_gateway"],
                details={"compose_service": "ollama", "gateway": "app/ai"},
            )
        )
    if "billing" in module_keys:
        components.append(
            InfraComponent(
                id="billing_runtime",
                name="Billing",
                category="commerce",
                reuse=True,
                platform_ref=PLATFORM_INFRA["billing"],
                details={"providers": ["stripe", "razorpay"]},
            )
        )
    deploy = blueprint.deployment or {}
    if deploy.get("ssl") or deploy.get("targets"):
        components.append(
            InfraComponent(
                id="tls",
                name="HTTPS / TLS",
                category="security",
                reuse=True,
                platform_ref="nginx + SSL manager",
                details={"ssl_mode_env": "SSL_MODE", "acme_email_env": "SSL_ACME_EMAIL"},
            )
        )
    return components


def generate_deployment_targets(
    blueprint: ProductBlueprint,
) -> List[InfraTarget]:
    preferred = {str(t).lower() for t in (blueprint.deployment or {}).get("targets") or []}
    # Always recommend existing VPS/Docker path first
    targets: List[InfraTarget] = []
    meta = {
        "docker": ("Primary local/prod compose stack", True, PLATFORM_INFRA["compose"]),
        "vps": ("Current Hostinger/VPS compose deploy", True, "deploy/ + docker-compose.prod.yml"),
        "coolify": ("Compose-compatible PaaS", True, "reuse compose file"),
        "railway": ("Managed containers — map env from .env.prod.example", False, None),
        "aws": ("ECS/EKS plan — reuse images, not a new runtime", False, None),
        "azure": ("ACA/AKS plan — reuse images", False, None),
        "google_cloud": ("Cloud Run/GKE plan — reuse images", False, None),
        "digitalocean": ("App Platform/Droplet — closest to VPS compose", True, "compose"),
        "kubernetes": ("Future scale-out — do not fork services", False, None),
    }
    for name in DEPLOYMENT_TARGETS:
        reason, reuse, ref = meta[name]
        score = 10 if name in {"docker", "vps"} else 5
        if name in preferred:
            score += 5
        if name == "docker" and "compose" in preferred:
            score += 3
        targets.append(
            InfraTarget(
                id=name,
                name=name.replace("_", " ").title(),
                recommended=name in {"docker", "vps"} or name in preferred,
                score=score,
                reuse_existing_stack=reuse,
                platform_ref=ref,
                reason=reason,
                planning_only=True,
                note="Planning only — Phase 7 does not deploy",
            )
        )
    targets.sort(key=lambda t: (-t.score, t.id))
    return targets


def generate_environment(
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    ai: Optional[AiManifest],
    backend: Optional[BackendManifest],
) -> List[InfraEnvVar]:
    module_keys = {m.key for m in modules}
    envs: List[InfraEnvVar] = [
        InfraEnvVar(key="APP_ENV", required=True, secret=False, group="core", example="production"),
        InfraEnvVar(key="PUBLIC_API_BASE_URL", required=True, secret=False, group="core", example="https://api.example.com"),
        InfraEnvVar(key="CORS_ORIGINS", required=True, secret=False, group="security", example='["https://app.example.com"]'),
        InfraEnvVar(key="JWT_SECRET_KEY", required=True, secret=True, group="auth", example="openssl rand -hex 32"),
        InfraEnvVar(key="JWT_REFRESH_SECRET_KEY", required=True, secret=True, group="auth", example="openssl rand -hex 32"),
        InfraEnvVar(key="DB_HOST", required=True, secret=False, group="postgres", example="db"),
        InfraEnvVar(key="DB_PASSWORD", required=True, secret=True, group="postgres", example="change-me"),
        InfraEnvVar(key="REDIS_HOST", required=True, secret=False, group="redis", example="redis"),
        InfraEnvVar(key="SSL_MODE", required=True, secret=False, group="tls", example="certbot"),
        InfraEnvVar(key="SSL_ACME_EMAIL", required=False, secret=False, group="tls", example="ops@example.com"),
        InfraEnvVar(key="BACKUP_RETENTION_DAYS", required=False, secret=False, group="backups", example="14"),
        InfraEnvVar(key="STORAGE_PROVIDER", required=False, secret=False, group="storage", example="local"),
        InfraEnvVar(key="EMAIL_PROVIDER", required=False, secret=False, group="email", example="smtp"),
    ]
    # AI providers
    providers = [p.provider for p in (ai.providers if ai else [])] or ["openai", "ollama"]
    for key, provider in OPTIONAL_SECRET_GROUPS["ai_providers"]:
        envs.append(
            InfraEnvVar(
                key=key,
                required=provider in providers and provider != "ollama",
                secret=True,
                group="ai_providers",
                example="",
                related_provider=provider,
            )
        )
    if "billing" in module_keys or (blueprint.billing or {}).get("enabled"):
        for key, provider in OPTIONAL_SECRET_GROUPS["payments"]:
            envs.append(
                InfraEnvVar(
                    key=key,
                    required=False,
                    secret=True,
                    group="payments",
                    example="",
                    related_provider=provider,
                )
            )
    if "storage" in module_keys:
        for key, provider in OPTIONAL_SECRET_GROUPS["storage"]:
            envs.append(
                InfraEnvVar(
                    key=key,
                    required=False,
                    secret=True,
                    group="storage",
                    example="",
                    related_provider=provider,
                )
            )
    for key, provider in OPTIONAL_SECRET_GROUPS["email"]:
        envs.append(
            InfraEnvVar(
                key=key,
                required=False,
                secret=key.endswith("PASSWORD"),
                group="email",
                example="",
                related_provider=provider,
            )
        )
    for key, provider in OPTIONAL_SECRET_GROUPS["analytics"]:
        envs.append(
            InfraEnvVar(
                key=key,
                required=False,
                secret=key == "METRICS_TOKEN",
                group="analytics",
                example="",
                related_provider=provider,
            )
        )
    # OpenAPI/custom scale hint
    if backend and backend.api.custom_endpoint_count > 10:
        envs.append(
            InfraEnvVar(
                key="WORKER_CONCURRENCY",
                required=False,
                secret=False,
                group="workers",
                example="2",
            )
        )
    return envs


def generate_env_example(envs: List[InfraEnvVar]) -> str:
    lines = [
        "# Generated by THTWAAT Studio Phase 7 — planning only",
        "# Copy to .env.prod and fill secrets. Reuses existing compose/deploy conventions.",
        "",
    ]
    current = None
    for env in envs:
        if env.group != current:
            current = env.group
            lines.append(f"# --- {current} ---")
        prefix = "" if env.required else "# "
        val = env.example or ""
        comment = "  # REQUIRED" if env.required else ("  # secret" if env.secret else "")
        lines.append(f"{prefix}{env.key}={val}{comment}")
    return "\n".join(lines) + "\n"


def security_review(
    *,
    blueprint: ProductBlueprint,
    components: List[InfraComponent],
    envs: List[InfraEnvVar],
    targets: List[InfraTarget],
) -> List[BlueprintWarning]:
    warnings: List[BlueprintWarning] = []
    deploy = blueprint.deployment or {}
    auth = blueprint.authentication or {}

    missing_required = [e.key for e in envs if e.required and e.secret]
    if missing_required:
        warnings.append(
            BlueprintWarning(
                code="infra_secrets_required",
                severity="warn",
                message=f"Required secrets must be set before go-live: {', '.join(missing_required[:8])}",
                field="environment",
            )
        )

    if not deploy.get("ssl") and "tls" not in {c.id for c in components}:
        warnings.append(
            BlueprintWarning(
                code="infra_missing_https",
                severity="error",
                message="HTTPS/TLS not planned — enable SSL_MODE=certbot and nginx 443.",
                field="https",
            )
        )
    elif not deploy.get("ssl"):
        warnings.append(
            BlueprintWarning(
                code="infra_https_verify",
                severity="warn",
                message="Confirm SSL_MODE=certbot (not simulate) for production HTTPS.",
                field="https",
            )
        )

    open_ports = ["80", "443"]
    warnings.append(
        BlueprintWarning(
            code="infra_open_ports",
            severity="info",
            message=f"Public ports planned: {', '.join(open_ports)}. Keep api/web_app internal via nginx only.",
            field="ports",
        )
    )

    if not (auth.get("jwt") or auth.get("rbac") or auth.get("methods")):
        warnings.append(
            BlueprintWarning(
                code="infra_weak_auth",
                severity="error",
                message="Blueprint auth looks weak/empty — JWT/RBAC required with existing Auth module.",
                field="auth",
            )
        )

    if "backups" not in {c.id for c in components}:
        warnings.append(
            BlueprintWarning(
                code="infra_missing_backups",
                severity="error",
                message="Backup plan missing.",
                field="backups",
            )
        )
    else:
        warnings.append(
            BlueprintWarning(
                code="infra_backup_retention",
                severity="info",
                message="Verify BACKUP_RETENTION_DAYS and restore drill before launch.",
                field="backups",
            )
        )

    if "monitoring" not in {c.id for c in components}:
        warnings.append(
            BlueprintWarning(
                code="infra_missing_monitoring",
                severity="error",
                message="Monitoring missing — reuse app/monitoring + Prometheus/Grafana.",
                field="monitoring",
            )
        )

    if any(t.id == "kubernetes" and t.recommended for t in targets):
        warnings.append(
            BlueprintWarning(
                code="infra_k8s_planning",
                severity="info",
                message="Kubernetes is planning-only — reuse existing images/services, do not fork runtimes.",
                field="targets",
            )
        )
    return warnings


def estimate_infra_cost(
    *,
    blueprint: ProductBlueprint,
    ai: Optional[AiManifest],
    components: List[InfraComponent],
) -> InfraCostEstimate:
    complexity = (blueprint.estimated_complexity or "medium").lower()
    base = {"low": 25.0, "medium": 60.0, "high": 140.0}.get(complexity, 60.0)
    # VPS/docker baseline
    infra = base
    if any(c.id == "ai_gateway_runtime" for c in components):
        infra += 15.0  # ollama/GPU-ish buffer on VPS
    storage = 5.0 + (3.0 if "storage" in {c.id for c in components} else 0.0)
    bandwidth = 8.0 if complexity == "high" else 4.0
    ai_cost = float((ai.cost.estimated_monthly_usd if ai and ai.cost else 0.0) or 0.0)
    total = round(infra + storage + bandwidth + ai_cost, 2)
    return InfraCostEstimate(
        currency="USD",
        infrastructure_usd=round(infra, 2),
        ai_usd=round(ai_cost, 2),
        storage_usd=round(storage, 2),
        bandwidth_usd=round(bandwidth, 2),
        monthly_total_usd=total,
        notes=[
            "Planning estimate only — not a billing invoice",
            "Assumes single VPS/docker-compose.prod.yml footprint",
            "AI cost imported from Phase 6 AI manifest when present",
            f"Complexity={complexity}",
        ],
        breakdown={
            "vps_or_compose": infra,
            "object_storage": storage,
            "egress": bandwidth,
            "ai_gateway_usage": ai_cost,
        },
    )


def summarize_infra(
    *,
    components: List[InfraComponent],
    targets: List[InfraTarget],
    envs: List[InfraEnvVar],
    warnings: List[BlueprintWarning],
    cost: InfraCostEstimate,
) -> InfraSummary:
    reused = sum(1 for c in components if c.reuse)
    reuse_pct = round(100.0 * reused / max(len(components), 1), 1)
    return InfraSummary(
        component_count=len(components),
        target_count=len(targets),
        env_var_count=len(envs),
        required_secret_count=sum(1 for e in envs if e.required and e.secret),
        warning_count=len(warnings),
        reuse_percent=reuse_pct,
        estimated_monthly_usd=cost.monthly_total_usd,
        warnings=warnings,
    )


def generate_infrastructure_manifest(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    backend: Optional[BackendManifest],
    ai: Optional[AiManifest],
    project_title: str,
    blueprint_version: int,
    build_plan_version: int,
    frontend_version: int,
    backend_version: int,
    ai_version: int,
) -> InfraManifest:
    components = generate_components(blueprint, modules, ai)
    targets = generate_deployment_targets(blueprint)
    envs = generate_environment(blueprint, modules, ai, backend)
    env_example = generate_env_example(envs)
    warnings = security_review(
        blueprint=blueprint, components=components, envs=envs, targets=targets
    )
    cost = estimate_infra_cost(blueprint=blueprint, ai=ai, components=components)
    summary = summarize_infra(
        components=components,
        targets=targets,
        envs=envs,
        warnings=warnings,
        cost=cost,
    )
    return InfraManifest(
        schema_version=1,
        product_name=project_title,
        industry=blueprint.industry,
        product_type=blueprint.product_type,
        runtime={
            "compose": PLATFORM_INFRA["compose"],
            "nginx": PLATFORM_INFRA["nginx"],
            "workers": PLATFORM_INFRA["workers"],
            "scheduler": PLATFORM_INFRA["scheduler"],
            "ai_gateway": PLATFORM_INFRA["ai_gateway"],
            "monitoring": PLATFORM_INFRA["monitoring"],
            "note": "Reuse existing production stack — never duplicate runtimes",
        },
        components=components,
        targets=targets,
        environment=envs,
        env_example=env_example,
        secrets={
            "required": [e.key for e in envs if e.required and e.secret],
            "optional": [e.key for e in envs if (not e.required) and e.secret],
        },
        security={
            "https": True,
            "internal_only_app_ports": True,
            "rate_limiting": True,
            "no_new_privileges": True,
            "cors_no_wildcard": True,
        },
        backups={
            "enabled": True,
            "path": "data/backups",
            "retention_days_env": "BACKUP_RETENTION_DAYS",
            "restore": ["pg_restore", "verify health", "alembic current"],
        },
        scaling={
            "api": "horizontal",
            "worker": "horizontal",
            "db": "vertical_first",
            "redis": "vertical_first",
        },
        cost=cost,
        summary=summary,
        traceability={
            "blueprint_version": blueprint_version,
            "build_plan_version": build_plan_version,
            "frontend_version": frontend_version,
            "backend_version": backend_version,
            "ai_version": ai_version,
            "composed_modules": [m.key for m in modules],
            "reuse_percent": summary.reuse_percent,
        },
        warnings=warnings,
        note="Infrastructure planning only — Phase 7 does not deploy or emit app source",
    )
