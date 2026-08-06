"""Studio Backend Generator — frontend + build plan → architecture manifests (no codegen / no deploy)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.studio.schemas import (
    BackendApiEndpoint,
    BackendApiManifest,
    BackendColumn,
    BackendDatabaseManifest,
    BackendManifest,
    BackendOpenApiPreview,
    BackendQueueItem,
    BackendRbacManifest,
    BackendRelationship,
    BackendServiceItem,
    BackendStorageItem,
    BackendSummary,
    BackendTable,
    BlueprintWarning,
    ComposedModule,
    FrontendManifest,
    FrontendPageSpec,
    ProductBlueprint,
)


# Existing platform API surfaces — never regenerate these modules
REUSE_API_CATALOG: Dict[str, Dict[str, Any]] = {
    "authentication": {
        "prefix": "/api/v1/auth",
        "resources": ["session", "otp", "password"],
        "platform_ref": "app/auth",
        "tags": ["Auth"],
    },
    "rbac": {
        "prefix": "/api/v1/auth",
        "resources": ["roles", "permissions"],
        "platform_ref": "app/auth",
        "tags": ["RBAC"],
        "alias_of": "authentication",
    },
    "billing": {
        "prefix": "/api/v1/payments",
        "resources": ["plans", "subscriptions", "invoices"],
        "platform_ref": "app/payments",
        "tags": ["Billing"],
    },
    "payments": {
        "prefix": "/api/v1/payments",
        "resources": ["checkout", "webhooks"],
        "platform_ref": "app/payments",
        "tags": ["Payments"],
        "alias_of": "billing",
    },
    "ai_agent": {
        "prefix": "/v2/agents",
        "resources": ["agents", "playground", "publish"],
        "platform_ref": "app/agent_platform",
        "tags": ["Agents"],
        "extra_prefixes": ["/api/v1/ai"],
    },
    "knowledge": {
        "prefix": "/v2/knowledge",
        "resources": ["bases", "documents", "chunks"],
        "platform_ref": "app/agent_platform/knowledge",
        "tags": ["Knowledge"],
    },
    "marketplace": {
        "prefix": "/api/v1/marketplace",
        "resources": ["templates", "installs", "favorites"],
        "platform_ref": "app/marketplace",
        "tags": ["Marketplace"],
    },
    "publisher": {
        "prefix": "/api/v1/agents",
        "resources": ["publish", "listings"],
        "platform_ref": "app/agent_platform/publish",
        "tags": ["Publisher"],
    },
    "analytics": {
        "prefix": "/api/v1/admin",
        "resources": ["analytics", "usage"],
        "platform_ref": "app/monitoring",
        "tags": ["Analytics"],
    },
    "admin": {
        "prefix": "/api/v1/admin",
        "resources": ["workspace", "users", "ops"],
        "platform_ref": "app/monitoring",
        "tags": ["Admin"],
    },
    "storage": {
        "prefix": "/api/v1/storage",
        "resources": ["files", "uploads"],
        "platform_ref": "app/storage",
        "tags": ["Storage"],
    },
    "notifications": {
        "prefix": "/api/v1/notifications",
        "resources": ["messages", "preferences"],
        "platform_ref": "app/notifications",
        "tags": ["Notifications"],
    },
    "widget": {
        "prefix": "/v2/agents",
        "resources": ["embed", "chat"],
        "platform_ref": "sdk/widget",
        "tags": ["Widget"],
        "alias_of": "ai_agent",
    },
    "database": {
        "prefix": "/api/v1",
        "resources": [],
        "platform_ref": "app/database",
        "tags": ["Database"],
    },
    "dashboard": {
        "prefix": "/api/v1",
        "resources": ["overview"],
        "platform_ref": "apps/templates/saas",
        "tags": ["Dashboard"],
    },
}

PLATFORM_TABLES: Dict[str, List[str]] = {
    "authentication": ["users", "sessions", "otp_codes"],
    "rbac": ["roles", "permissions", "role_permissions"],
    "billing": ["plans", "subscriptions", "invoices"],
    "payments": ["payment_intents", "payment_webhooks"],
    "ai_agent": ["agent_configs", "agent_api_keys", "conversations"],
    "knowledge": ["knowledge_bases", "documents", "chunks"],
    "marketplace": ["marketplace_templates", "template_installs"],
    "publisher": ["publisher_listings"],
    "storage": ["storage_objects"],
    "notifications": ["notifications"],
    "analytics": ["usage_events"],
    "admin": ["audit_logs"],
}

FIELD_TYPE_MAP = {
    "string": "varchar",
    "email": "varchar",
    "password": "varchar",
    "number": "numeric",
    "date": "date",
    "datetime": "timestamptz",
    "select": "varchar",
    "textarea": "text",
    "uuid": "uuid",
    "boolean": "boolean",
    "json": "jsonb",
}


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s[:64] or "resource"


def _snake(value: str) -> str:
    return _slug(value).replace("-", "_")


def _perm(resource: str, action: str) -> str:
    return f"{_snake(resource)}:{action}"


def _crud_ops() -> List[str]:
    return ["list", "create", "get", "update", "delete"]


def _endpoints_for_resource(
    *,
    resource: str,
    prefix: str,
    reuse: bool,
    module_key: str,
    platform_ref: Optional[str],
    tags: List[str],
    fields: Optional[List[Dict[str, Any]]] = None,
) -> List[BackendApiEndpoint]:
    base = f"{prefix.rstrip('/')}/{_slug(resource)}"
    ops = [
        ("GET", base, "list", True, True, True),
        ("POST", base, "create", False, False, False),
        ("GET", f"{base}/{{id}}", "get", False, False, False),
        ("PUT", f"{base}/{{id}}", "update", False, False, False),
        ("DELETE", f"{base}/{{id}}", "delete", False, False, False),
    ]
    out: List[BackendApiEndpoint] = []
    for method, path, action, paginate, search, filters in ops:
        out.append(
            BackendApiEndpoint(
                id=f"{_snake(resource)}_{action}",
                method=method,
                path=path,
                resource=_snake(resource),
                operation=action,
                summary=f"{action.title()} {resource}",
                permissions=[_perm(resource, action if action != "get" else "read")],
                validation={
                    "body_fields": [f.get("name") for f in (fields or []) if action in {"create", "update"}]
                },
                filters=["status", "q"] if filters else [],
                pagination=paginate,
                search=search,
                upload=False,
                reuse=reuse,
                module_key=module_key,
                platform_ref=platform_ref,
                tags=tags,
            )
        )
    return out


def generate_api_manifest(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
) -> BackendApiManifest:
    endpoints: List[BackendApiEndpoint] = []
    seen_paths: Set[str] = set()
    module_keys = {m.key for m in modules}

    def add_eps(eps: List[BackendApiEndpoint]) -> None:
        for ep in eps:
            key = f"{ep.method}:{ep.path}"
            if key in seen_paths:
                continue
            seen_paths.add(key)
            endpoints.append(ep)

    for mod in modules:
        if mod.key.startswith("custom:") or mod.key == "deployment":
            continue
        catalog = REUSE_API_CATALOG.get(mod.key)
        if not catalog:
            continue
        if catalog.get("alias_of") and catalog["alias_of"] in module_keys:
            continue
        for resource in catalog.get("resources") or ["resource"]:
            add_eps(
                _endpoints_for_resource(
                    resource=resource,
                    prefix=str(catalog["prefix"]),
                    reuse=True,
                    module_key=mod.key,
                    platform_ref=str(catalog.get("platform_ref") or mod.platform_ref),
                    tags=list(catalog.get("tags") or [mod.label]),
                )
            )
        # Webhooks for billing
        if mod.key == "billing":
            add_eps(
                [
                    BackendApiEndpoint(
                        id="billing_webhook",
                        method="POST",
                        path="/api/v1/payments/webhooks/stripe",
                        resource="webhooks",
                        operation="receive",
                        summary="Stripe webhook",
                        permissions=[],
                        reuse=True,
                        module_key="billing",
                        platform_ref="app/payments",
                        tags=["Billing", "Webhooks"],
                    )
                ]
            )

    # Custom resources from frontend CRUD pages / blueprint tables
    custom_pages: List[FrontendPageSpec] = []
    if frontend:
        custom_pages = [p for p in frontend.pages if p.kind == "generated_spec" and p.crud]

    custom_tables: Set[str] = set()
    for page in custom_pages:
        assert page.crud
        table = page.crud.table
        custom_tables.add(table)
        fields = [f.model_dump() for f in page.crud.fields]
        add_eps(
            _endpoints_for_resource(
                resource=page.crud.entity,
                prefix="/api/v1/custom",
                reuse=False,
                module_key=page.module_key or f"custom:{table}",
                platform_ref=None,
                tags=["Custom", page.title],
                fields=fields,
            )
        )
        # upload endpoint when storage likely needed
        add_eps(
            [
                BackendApiEndpoint(
                    id=f"{_snake(page.crud.entity)}_upload",
                    method="POST",
                    path=f"/api/v1/custom/{_slug(page.crud.entity)}/upload",
                    resource=_snake(page.crud.entity),
                    operation="upload",
                    summary=f"Upload for {page.title}",
                    permissions=[_perm(page.crud.entity, "update")],
                    upload=True,
                    reuse=False,
                    module_key=page.module_key,
                    tags=["Custom", "Uploads"],
                )
            ]
        )

    for table in blueprint.database_tables:
        if table.lower() in {"users", "sessions"}:
            continue
        if table in custom_tables:
            continue
        # skip platform tables
        platform_flat = {t for ts in PLATFORM_TABLES.values() for t in ts}
        if table in platform_flat:
            continue
        # only if not already covered
        if any(ep.resource == _snake(table) for ep in endpoints):
            continue
        add_eps(
            _endpoints_for_resource(
                resource=table.rstrip("s") if table.endswith("s") else table,
                prefix="/api/v1/custom",
                reuse=False,
                module_key=f"custom:{table}",
                platform_ref=None,
                tags=["Custom"],
            )
        )

    reused = sum(1 for e in endpoints if e.reuse)
    return BackendApiManifest(
        endpoints=endpoints,
        resource_count=len({e.resource for e in endpoints}),
        reuse_endpoint_count=reused,
        custom_endpoint_count=len(endpoints) - reused,
    )


def _columns_from_fields(fields: List[Dict[str, Any]]) -> List[BackendColumn]:
    cols = [
        BackendColumn(name="id", type="uuid", primary_key=True, nullable=False),
        BackendColumn(name="workspace_id", type="uuid", nullable=False, indexed=True),
    ]
    seen = {"id", "workspace_id"}
    for f in fields:
        name = str(f.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cols.append(
            BackendColumn(
                name=name,
                type=FIELD_TYPE_MAP.get(str(f.get("type") or "string"), "varchar"),
                nullable=not bool(f.get("required")),
                indexed=bool(f.get("list_column")),
            )
        )
    cols.append(BackendColumn(name="created_at", type="timestamptz", nullable=False))
    cols.append(BackendColumn(name="updated_at", type="timestamptz", nullable=False))
    return cols


def generate_database_manifest(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
) -> BackendDatabaseManifest:
    tables: List[BackendTable] = []
    relationships: List[BackendRelationship] = []
    enums: List[Dict[str, Any]] = [
        {"name": "record_status", "values": ["active", "archived", "deleted"]},
    ]
    seen: Set[str] = set()
    module_keys = {m.key for m in modules}

    def add_table(table: BackendTable) -> None:
        if table.name in seen:
            return
        seen.add(table.name)
        tables.append(table)

    for mod in modules:
        if mod.key.startswith("custom:") or mod.key == "deployment":
            continue
        if mod.key in REUSE_API_CATALOG and REUSE_API_CATALOG[mod.key].get("alias_of"):
            alias = REUSE_API_CATALOG[mod.key]["alias_of"]
            if alias in module_keys:
                continue
        for tname in PLATFORM_TABLES.get(mod.key, []):
            add_table(
                BackendTable(
                    name=tname,
                    reuse=True,
                    module_key=mod.key,
                    platform_ref=REUSE_API_CATALOG.get(mod.key, {}).get("platform_ref"),
                    columns=[
                        BackendColumn(name="id", type="uuid", primary_key=True, nullable=False),
                        BackendColumn(name="workspace_id", type="uuid", nullable=False, indexed=True),
                        BackendColumn(name="created_at", type="timestamptz", nullable=False),
                        BackendColumn(name="updated_at", type="timestamptz", nullable=False),
                    ],
                    indexes=[["workspace_id"], ["created_at"]],
                    constraints=["fk_workspace"],
                    migration=f"reuse_existing_{tname}",
                )
            )

    # Custom tables from frontend CRUD
    if frontend:
        for page in frontend.pages:
            if not page.crud:
                continue
            tname = page.crud.table
            fields = [f.model_dump() for f in page.crud.fields]
            add_table(
                BackendTable(
                    name=tname,
                    reuse=False,
                    module_key=page.module_key or f"custom:{tname}",
                    columns=_columns_from_fields(fields),
                    indexes=[["workspace_id"], ["created_at"]],
                    constraints=["fk_workspace", "pk_id"],
                    migration=f"create_{tname}",
                )
            )
            relationships.append(
                BackendRelationship(
                    from_table=tname,
                    to_table="users",
                    type="many_to_one",
                    foreign_key="workspace_id",
                    via="companies/users tenancy",
                )
            )

    # Blueprint tables not yet covered
    for tname in blueprint.database_tables:
        if tname in seen:
            continue
        add_table(
            BackendTable(
                name=tname,
                reuse=False,
                module_key=f"custom:{tname}",
                columns=_columns_from_fields(
                    [{"name": "name", "type": "string", "required": True, "list_column": True}]
                ),
                indexes=[["workspace_id"]],
                constraints=["fk_workspace"],
                migration=f"create_{tname}",
            )
        )

    reused = sum(1 for t in tables if t.reuse)
    return BackendDatabaseManifest(
        tables=tables,
        relationships=relationships,
        enums=enums,
        migrations=[t.migration for t in tables if t.migration],
        reuse_table_count=reused,
        custom_table_count=len(tables) - reused,
    )


def generate_service_manifest(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
) -> List[BackendServiceItem]:
    services: List[BackendServiceItem] = []
    module_keys = {m.key for m in modules}

    reuse_services = [
        ("authentication", "AuthService", "app/auth", ["login", "otp", "session"]),
        ("billing", "BillingService", "app/payments", ["subscribe", "invoice", "meter"]),
        ("ai_agent", "AgentService", "app/agent_platform", ["chat", "publish", "quota"]),
        ("knowledge", "KnowledgeService", "app/agent_platform/knowledge", ["ingest", "retrieve"]),
        ("marketplace", "MarketplaceService", "app/marketplace", ["browse", "install"]),
        ("publisher", "PublishService", "app/agent_platform/publish", ["package", "release"]),
        ("notifications", "NotificationService", "app/notifications", ["email", "push"]),
        ("storage", "StorageService", "app/storage", ["upload", "signed_url"]),
        ("analytics", "UsageService", "app/usage", ["meter", "report"]),
        ("admin", "AdminOpsService", "app/monitoring", ["audit", "health"]),
    ]
    for key, name, ref, caps in reuse_services:
        if key not in module_keys:
            continue
        services.append(
            BackendServiceItem(
                id=_snake(name),
                name=name,
                kind="business",
                reuse=True,
                module_key=key,
                platform_ref=ref,
                capabilities=caps,
                events=[f"{key}.changed"],
            )
        )

    # Background / webhook services
    if "billing" in module_keys:
        services.append(
            BackendServiceItem(
                id="payment_webhook_worker",
                name="PaymentWebhookWorker",
                kind="webhook",
                reuse=True,
                module_key="billing",
                platform_ref="app/payments",
                capabilities=["stripe_webhook", "razorpay_webhook"],
                events=["payment.succeeded", "payment.failed"],
            )
        )
    if "notifications" in module_keys or "email" in {i.lower() for i in blueprint.integrations}:
        services.append(
            BackendServiceItem(
                id="email_job",
                name="EmailJob",
                kind="job",
                reuse=True,
                module_key="notifications",
                platform_ref="app/notifications",
                capabilities=["send_email"],
                events=["email.queued"],
            )
        )

    # Custom domain services from frontend CRUD
    if frontend:
        for page in frontend.pages:
            if not page.crud:
                continue
            entity = page.crud.entity
            services.append(
                BackendServiceItem(
                    id=f"{_snake(entity)}_service",
                    name=f"{entity.title().replace('_', '')}Service",
                    kind="business",
                    reuse=False,
                    module_key=page.module_key or f"custom:{page.crud.table}",
                    capabilities=["crud", "validate", "search"],
                    events=[f"{_snake(entity)}.created", f"{_snake(entity)}.updated"],
                )
            )

    for wf in blueprint.workflows:
        services.append(
            BackendServiceItem(
                id=f"workflow_{_snake(wf)}",
                name=f"{wf.replace('_', ' ').title()} Workflow",
                kind="event",
                reuse=False,
                module_key="custom:workflow",
                capabilities=["orchestrate"],
                events=[f"workflow.{_snake(wf)}"],
            )
        )
    return services


def generate_rbac_manifest(
    *,
    blueprint: ProductBlueprint,
    api: BackendApiManifest,
) -> BackendRbacManifest:
    roles = list(blueprint.roles) or ["company_owner", "admin", "member"]
    if "company_owner" not in [r.lower() for r in roles]:
        roles = ["company_owner", *roles]

    permissions: List[str] = list(blueprint.permissions or [])
    for ep in api.endpoints:
        permissions.extend(ep.permissions)
    permissions = sorted({p for p in permissions if p})

    policies: List[Dict[str, Any]] = []
    for role in roles:
        low = role.lower()
        if low in {"company_owner", "admin", "super_admin"}:
            policies.append({"role": role, "allow": ["*"], "deny": []})
        elif "doctor" in low or "manager" in low:
            policies.append(
                {
                    "role": role,
                    "allow": [p for p in permissions if not p.endswith(":delete")],
                    "deny": [p for p in permissions if p.endswith(":delete")],
                }
            )
        else:
            policies.append(
                {
                    "role": role,
                    "allow": [p for p in permissions if p.endswith(":read") or p.endswith(":list")],
                    "deny": [p for p in permissions if p.endswith(":delete")],
                }
            )

    return BackendRbacManifest(
        roles=roles,
        permissions=permissions,
        policies=policies,
        reuse=True,
        platform_ref="app/auth",
        note="RBAC reuses Auth tenancy — do not invent a parallel ACL stack",
    )


def generate_storage_plan(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
) -> List[BackendStorageItem]:
    items: List[BackendStorageItem] = []
    module_keys = {m.key for m in modules}
    if "storage" in module_keys or "storage" in {i.lower() for i in blueprint.integrations}:
        items.append(
            BackendStorageItem(
                id="uploads",
                kind="files",
                path="uploads/{workspace_id}/",
                reuse=True,
                module_key="storage",
                platform_ref="app/storage",
            )
        )
        items.append(
            BackendStorageItem(
                id="images",
                kind="images",
                path="images/{workspace_id}/",
                reuse=True,
                module_key="storage",
                platform_ref="app/storage",
            )
        )
        items.append(
            BackendStorageItem(
                id="documents",
                kind="documents",
                path="documents/{workspace_id}/",
                reuse=True,
                module_key="storage",
                platform_ref="app/storage",
            )
        )
    if "knowledge" in module_keys or (blueprint.knowledge or {}).get("enabled"):
        items.append(
            BackendStorageItem(
                id="knowledge_docs",
                kind="knowledge",
                path="knowledge/{workspace_id}/",
                reuse=True,
                module_key="knowledge",
                platform_ref="app/agent_platform/knowledge",
            )
        )
    if frontend:
        for page in frontend.pages:
            if page.crud and any(f.type == "textarea" for f in page.crud.fields):
                items.append(
                    BackendStorageItem(
                        id=f"attach_{_snake(page.crud.entity)}",
                        kind="documents",
                        path=f"custom/{_snake(page.crud.table)}/{{id}}/",
                        reuse=False,
                        module_key=page.module_key,
                    )
                )
    return items


def generate_queue_plan(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
) -> List[BackendQueueItem]:
    module_keys = {m.key for m in modules}
    queues: List[BackendQueueItem] = []
    if "notifications" in module_keys or "email" in {i.lower() for i in blueprint.integrations}:
        queues.append(
            BackendQueueItem(
                id="emails",
                name="emails",
                kind="emails",
                reuse=True,
                module_key="notifications",
                workers=["email_worker"],
                events=["email.send"],
            )
        )
        queues.append(
            BackendQueueItem(
                id="notifications",
                name="notifications",
                kind="notifications",
                reuse=True,
                module_key="notifications",
                workers=["notification_worker"],
                events=["notification.push"],
            )
        )
    if "ai_agent" in module_keys or blueprint.ai_features:
        queues.append(
            BackendQueueItem(
                id="ai_jobs",
                name="ai_jobs",
                kind="ai_jobs",
                reuse=True,
                module_key="ai_agent",
                workers=["ai_worker"],
                events=["ai.generate", "ai.embed"],
            )
        )
    if "knowledge" in module_keys:
        queues.append(
            BackendQueueItem(
                id="knowledge_ingest",
                name="knowledge_ingest",
                kind="imports",
                reuse=True,
                module_key="knowledge",
                workers=["ingest_worker"],
                events=["knowledge.ingest"],
            )
        )
    queues.append(
        BackendQueueItem(
            id="imports",
            name="imports",
            kind="imports",
            reuse=False,
            module_key="custom:imports",
            workers=["import_worker"],
            events=["import.started"],
        )
    )
    queues.append(
        BackendQueueItem(
            id="exports",
            name="exports",
            kind="exports",
            reuse=False,
            module_key="custom:exports",
            workers=["export_worker"],
            events=["export.started"],
        )
    )
    return queues


def generate_openapi_preview(
    *,
    product_name: str,
    api: BackendApiManifest,
) -> BackendOpenApiPreview:
    paths: Dict[str, Any] = {}
    for ep in api.endpoints:
        path_item = paths.setdefault(ep.path, {})
        path_item[ep.method.lower()] = {
            "operationId": ep.id,
            "summary": ep.summary,
            "tags": ep.tags,
            "security": [{"bearerAuth": []}] if ep.permissions else [],
            "parameters": (
                [{"name": "limit", "in": "query", "schema": {"type": "integer"}}]
                if ep.pagination
                else []
            )
            + (
                [{"name": "q", "in": "query", "schema": {"type": "string"}}]
                if ep.search
                else []
            ),
            "x-reuse": ep.reuse,
            "x-module": ep.module_key,
        }
    return BackendOpenApiPreview(
        openapi="3.0.3",
        info={
            "title": f"{product_name} API",
            "version": "0.1.0-preview",
            "description": "Studio backend preview — no codegen. Reuse existing platform routes where marked x-reuse.",
        },
        paths=paths,
        components={
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
    )


def summarize_backend(
    *,
    api: BackendApiManifest,
    database: BackendDatabaseManifest,
    services: List[BackendServiceItem],
    rbac: BackendRbacManifest,
    storage: List[BackendStorageItem],
    queues: List[BackendQueueItem],
) -> BackendSummary:
    total_eps = max(len(api.endpoints), 1)
    total_tables = max(len(database.tables), 1)
    reuse_api = round(100.0 * api.reuse_endpoint_count / total_eps, 1)
    reuse_db = round(100.0 * database.reuse_table_count / total_tables, 1)
    reuse_svc = round(
        100.0 * sum(1 for s in services if s.reuse) / max(len(services), 1),
        1,
    )
    reuse_pct = round((reuse_api + reuse_db + reuse_svc) / 3.0, 1)
    custom_work = "none"
    custom_score = api.custom_endpoint_count + database.custom_table_count + sum(
        1 for s in services if not s.reuse
    )
    if custom_score == 0:
        custom_work = "none"
    elif custom_score <= 6:
        custom_work = "low"
    elif custom_score <= 15:
        custom_work = "medium"
    else:
        custom_work = "high"

    warnings: List[BlueprintWarning] = []
    if reuse_pct < 60:
        warnings.append(
            BlueprintWarning(
                code="backend_low_reuse",
                severity="warn",
                message=f"Backend reuse is {reuse_pct}% — prefer Auth/Billing/AI/Marketplace modules.",
                field="reuse_percent",
            )
        )
    forbidden_dupes = {
        "auth",
        "billing",
        "ai gateway",
        "marketplace",
        "agents",
        "knowledge",
        "publisher",
        "analytics",
        "monitoring",
        "admin",
    }
    for s in services:
        if not s.reuse and any(d in s.name.lower() for d in forbidden_dupes):
            warnings.append(
                BlueprintWarning(
                    code="backend_duplicate_platform_module",
                    severity="error",
                    message=f"Custom service “{s.name}” looks like a platform duplicate — reuse instead.",
                    field="services",
                )
            )
    if not rbac.roles:
        warnings.append(
            BlueprintWarning(
                code="backend_missing_rbac",
                severity="error",
                message="RBAC roles missing.",
                field="rbac",
            )
        )
    return BackendSummary(
        endpoint_count=len(api.endpoints),
        table_count=len(database.tables),
        service_count=len(services),
        role_count=len(rbac.roles),
        storage_item_count=len(storage),
        queue_count=len(queues),
        reuse_percent=reuse_pct,
        estimated_custom_work=custom_work,
        warnings=warnings,
    )


def generate_backend_manifest(
    *,
    blueprint: ProductBlueprint,
    modules: List[ComposedModule],
    frontend: Optional[FrontendManifest],
    project_title: str,
    blueprint_version: int,
    build_plan_version: int,
    frontend_version: int,
) -> BackendManifest:
    api = generate_api_manifest(blueprint=blueprint, modules=modules, frontend=frontend)
    database = generate_database_manifest(
        blueprint=blueprint, modules=modules, frontend=frontend
    )
    services = generate_service_manifest(
        blueprint=blueprint, modules=modules, frontend=frontend
    )
    rbac = generate_rbac_manifest(blueprint=blueprint, api=api)
    storage = generate_storage_plan(
        blueprint=blueprint, modules=modules, frontend=frontend
    )
    queues = generate_queue_plan(blueprint=blueprint, modules=modules)
    openapi = generate_openapi_preview(product_name=project_title, api=api)
    summary = summarize_backend(
        api=api,
        database=database,
        services=services,
        rbac=rbac,
        storage=storage,
        queues=queues,
    )

    return BackendManifest(
        schema_version=1,
        product_name=project_title,
        industry=blueprint.industry,
        product_type=blueprint.product_type,
        api=api,
        database=database,
        services=services,
        rbac=rbac,
        storage=storage,
        queues=queues,
        openapi=openapi,
        summary=summary,
        traceability={
            "blueprint_version": blueprint_version,
            "build_plan_version": build_plan_version,
            "frontend_version": frontend_version,
            "composed_modules": [m.key for m in modules],
            "reuse_percent": summary.reuse_percent,
        },
        warnings=summary.warnings,
        note="Architecture preview only — Phase 5 does not emit source code or deploy",
    )
