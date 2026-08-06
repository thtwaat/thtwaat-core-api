"""Production AI Product Architect — AI Gateway first, heuristic fallback only."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.product_generator.analyzer import analyze_prompt
from app.studio.schemas import (
    BlueprintRecommendations,
    BlueprintWarning,
    ProductBlueprint,
)

logger = logging.getLogger(__name__)

ARCHITECT_SYSTEM = """You are THTWAAT Product Architect, a senior SaaS systems designer.
Analyze the product idea and return ONLY one JSON object (no markdown fences, no prose).

Required keys (use exactly these names):
- industry (string): e.g. healthcare, restaurant, crm, education, ecommerce, finance, saas, real_estate, legal, hospitality, logistics, hr
- product_type (string): saas | website | landing | crm | ecommerce | helpdesk | marketplace
- target_users (string array)
- pages (string array): concrete UI screens (Landing, Login, Admin, …)
- dashboard_modules (string array)
- backend_modules (string array): Auth, Users, RBAC, Billing, AI Gateway, Knowledge, Jobs, Storage, …
- database_tables (string array): snake_case table names
- roles (string array)
- permissions (string array): resource:action style
- authentication (object): methods[], mfa (bool), rbac (bool), jwt (bool), oauth_providers[]
- billing (object): enabled (bool), plans[], metering (bool), trials (bool)
- payments (object): providers[], currencies[], region_pricing (bool)
- ai_features (string array): chat, rag, memory, streaming, tools, vision, voice, appointment_assistant, …
- knowledge (object): enabled (bool), rag (bool), packs[]
- workflows (string array): business processes
- integrations (string array): stripe, razorpay, email, sms, webhooks, storage, calendar, …
- deployment (object): targets[], ssl (bool), healthchecks (bool), workers (bool), monitoring (bool), regions[]
- marketplace_category (string)
- estimated_complexity (string): low | medium | high
- estimated_build_time (string)

Rules:
1. Infer industry accurately from domain language (hospital→healthcare, clinic→healthcare, POS→retail, etc.).
2. Include Admin when a multi-tenant SaaS/dashboard is implied.
3. Include Auth/JWT/RBAC for any app with users.
4. Include billing+payments when SaaS, subscriptions, invoices, or monetization is implied.
5. Include AI features only when the prompt asks for AI/chat/RAG/voice/vision/agents.
6. Prefer snake_case for database_tables.
7. Do NOT generate application source code.
8. Prefer THTWAAT platform primitives: Agents, Knowledge, Billing, Marketplace, Domains, Widgets.
"""

PROVIDER_DEFAULT_MODELS: Dict[str, str] = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "anthropic": "claude-3-5-haiku-latest",
    "claude": "claude-3-5-haiku-latest",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
}

REQUIRED_BLUEPRINT_KEYS = (
    "industry",
    "product_type",
    "pages",
    "backend_modules",
    "database_tables",
    "roles",
    "authentication",
    "billing",
    "ai_features",
    "integrations",
    "deployment",
    "workflows",
)


def _uniq(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        key = str(item).strip()
        if not key:
            continue
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(key)
    return out


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _uniq([p.strip() for p in re.split(r"[\n,;]", value) if p.strip()])
    if isinstance(value, list):
        return _uniq([str(x).strip() for x in value if str(x).strip()])
    return []


def _as_obj(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def normalize_ai_blueprint(raw: Dict[str, Any]) -> ProductBlueprint:
    """Normalize AI JSON into ProductBlueprint without injecting heuristic domain content."""
    auth = _as_obj(raw.get("authentication"))
    billing = _as_obj(raw.get("billing"))
    payments = _as_obj(raw.get("payments"))
    knowledge = _as_obj(raw.get("knowledge"))
    deployment = _as_obj(raw.get("deployment"))

    if "jwt" not in auth:
        auth["jwt"] = True
    if "rbac" not in auth:
        auth["rbac"] = True
    if "methods" not in auth or not auth.get("methods"):
        auth["methods"] = ["email_password"]
    if "enabled" not in billing:
        billing["enabled"] = bool(billing.get("plans") or billing.get("metering"))
    if "enabled" not in knowledge:
        knowledge["enabled"] = bool(knowledge.get("rag") or knowledge.get("packs"))
    if "targets" not in deployment or not deployment.get("targets"):
        deployment["targets"] = ["docker", "compose"]
    if "ssl" not in deployment:
        deployment["ssl"] = True

    data = {
        "industry": str(raw.get("industry") or "general").strip().lower() or "general",
        "product_type": str(raw.get("product_type") or "saas").strip().lower() or "saas",
        "target_users": _as_str_list(raw.get("target_users")),
        "pages": _as_str_list(raw.get("pages")),
        "dashboard_modules": _as_str_list(raw.get("dashboard_modules")),
        "backend_modules": _as_str_list(raw.get("backend_modules")),
        "database_tables": _as_str_list(raw.get("database_tables")),
        "roles": _as_str_list(raw.get("roles")),
        "permissions": _as_str_list(raw.get("permissions")),
        "authentication": auth,
        "billing": billing,
        "payments": payments,
        "ai_features": _as_str_list(raw.get("ai_features")),
        "knowledge": knowledge,
        "workflows": _as_str_list(raw.get("workflows")),
        "integrations": _as_str_list(raw.get("integrations")),
        "deployment": deployment,
        "marketplace_category": str(
            raw.get("marketplace_category") or raw.get("product_type") or "saas"
        )
        .strip()
        .lower()
        or "saas",
        "estimated_complexity": str(raw.get("estimated_complexity") or "medium").strip().lower(),
        "estimated_build_time": str(raw.get("estimated_build_time") or "2-4 weeks").strip(),
    }
    return ProductBlueprint.model_validate(data)


def ai_blueprint_is_usable(blueprint: ProductBlueprint) -> bool:
    """Reject empty/near-empty AI payloads so we can fall back cleanly."""
    score = (
        len(blueprint.pages)
        + len(blueprint.database_tables)
        + len(blueprint.backend_modules)
        + len(blueprint.roles)
        + len(blueprint.workflows)
        + len(blueprint.integrations)
    )
    if score < 6:
        return False
    if not (blueprint.industry or "").strip():
        return False
    if not blueprint.pages and not blueprint.database_tables:
        return False
    return True


def build_heuristic_blueprint(prompt: str) -> ProductBlueprint:
    """Offline/fallback architect only — used when AI Gateway fails."""
    analysis = analyze_prompt(prompt)
    industry = analysis.industry or "general"
    product_type = analysis.product_type or "saas"
    features = list(analysis.required_features or [])
    text = prompt.lower()

    pages = ["Landing", "Login", "Register", "Dashboard", "Settings"]
    if "admin" in text or product_type in {"saas", "crm"}:
        pages.append("Admin")
    if "website" in text or product_type in {"website", "landing"}:
        pages.extend(["About", "Contact"])
    if "booking" in features or "appointment" in text:
        pages.append("Appointments")
    if "billing" in text or "payments" in features:
        pages.extend(["Billing", "Invoices"])
    if "patient" in text:
        pages.extend(["Patients", "Medical Records"])
    if "crm" in text or industry == "crm":
        pages.extend(["Customers", "Leads", "Pipeline"])

    dashboard_modules = ["Overview", "Activity", "Reports"]
    if "analytics" in features:
        dashboard_modules.append("Analytics")
    if "billing" in text or "payments" in features:
        dashboard_modules.append("Revenue")
    if "booking" in features:
        dashboard_modules.append("Schedule")

    backend_modules = ["Auth", "Users", "RBAC", "API", "Storage", "Notifications", "Jobs"]
    if "payments" in features or "billing" in text:
        backend_modules.extend(["Billing", "Payments", "Invoices"])
    if "ai_chat" in features or "ai" in text:
        backend_modules.extend(["AI Gateway", "Agents"])
    if "knowledge" in features or "rag" in text:
        backend_modules.append("Knowledge")
    if "domains" in features:
        backend_modules.append("Domains")

    tables = ["users", "companies", "roles", "sessions", "audit_logs"]
    if "patient" in text:
        tables.extend(["patients", "appointments", "doctors", "departments"])
    if "crm" in text or industry == "crm":
        tables.extend(["customers", "leads", "deals", "activities"])
    if "billing" in text or "payments" in features:
        tables.extend(["plans", "subscriptions", "invoices", "payments"])
    if "ai_chat" in features:
        tables.extend(["agents", "conversations", "messages"])
    if "knowledge" in features:
        tables.extend(["knowledge_bases", "documents", "chunks"])
    if "booking" in features and "appointments" not in tables:
        tables.append("bookings")

    roles = ["company_owner", "admin", "member"]
    if "doctor" in text or industry == "healthcare":
        roles.extend(["doctor", "receptionist", "patient"])
    if "crm" in text:
        roles.extend(["sales_rep", "sales_manager"])

    permissions = [
        "users:read",
        "users:manage",
        "settings:read",
        "settings:manage",
        "analytics:read",
    ]
    if "payments" in features or "billing" in text:
        permissions.extend(["billing:read", "billing:manage"])
    if "ai_chat" in features:
        permissions.extend(["agents:read", "agents:manage"])

    ai_features: List[str] = []
    if "ai_chat" in features or "chat" in text:
        ai_features.append("chat")
    if "knowledge" in features or "rag" in text:
        ai_features.extend(["rag", "memory"])
    if "booking" in features or "appointment" in text:
        ai_features.append("appointment_assistant")
    if "vision" in text:
        ai_features.append("vision")
    if "voice" in text:
        ai_features.append("voice")
    if not ai_features and "ai" in text:
        ai_features.append("chat")

    complexity = "low"
    score = len(pages) + len(tables) + len(backend_modules)
    if score > 35:
        complexity = "high"
    elif score > 22:
        complexity = "medium"

    build_time = {"low": "1-2 weeks", "medium": "2-4 weeks", "high": "4-8 weeks"}[complexity]
    category = analysis.category or product_type or "saas"

    return ProductBlueprint(
        industry=industry,
        product_type=product_type,
        target_users=_uniq(
            [
                "Business owners",
                "Admins",
                "Staff",
                *(["Patients", "Doctors"] if industry == "healthcare" else []),
                *(["Sales team"] if industry == "crm" else []),
            ]
        ),
        pages=_uniq(pages),
        dashboard_modules=_uniq(dashboard_modules),
        backend_modules=_uniq(backend_modules),
        database_tables=_uniq(tables),
        roles=_uniq(roles),
        permissions=_uniq(permissions),
        authentication={
            "methods": ["email_password", "otp"],
            "mfa": True,
            "rbac": True,
            "jwt": True,
        },
        billing={
            "enabled": "billing" in text or "payments" in features or "subscription" in text,
            "plans": ["free", "starter", "pro"],
            "metering": True,
        },
        payments={
            "providers": ["stripe", "razorpay"],
            "region_pricing": True,
        },
        ai_features=_uniq(ai_features),
        knowledge={
            "enabled": "knowledge" in features or "rag" in text or bool(ai_features),
            "rag": "rag" in text or "knowledge" in features,
            "packs": [],
        },
        workflows=_uniq(
            [
                *(["appointment_booking"] if "booking" in features or "appointment" in text else []),
                *(["lead_capture"] if "leads" in features else []),
                *(["human_handoff"] if "ai_chat" in features else []),
                "user_onboarding",
            ]
        ),
        integrations=_uniq(
            [
                *(["stripe", "razorpay"] if "payments" in features or "billing" in text else []),
                "email",
                "webhooks",
                "storage",
            ]
        ),
        deployment={
            "targets": ["docker", "compose"],
            "ssl": True,
            "healthchecks": True,
            "workers": True,
            "monitoring": True,
        },
        marketplace_category=str(category),
        estimated_complexity=complexity,
        estimated_build_time=build_time,
    )


def validate_blueprint(blueprint: ProductBlueprint) -> List[BlueprintWarning]:
    warnings: List[BlueprintWarning] = []
    pages_l = {p.lower() for p in blueprint.pages}
    modules_l = {m.lower() for m in blueprint.backend_modules}
    tables_l = {t.lower() for t in blueprint.database_tables}
    roles_l = {r.lower() for r in blueprint.roles}
    ai = [a.lower() for a in blueprint.ai_features]
    auth = blueprint.authentication or {}
    billing = blueprint.billing or {}
    payments = blueprint.payments or {}
    deployment = blueprint.deployment or {}
    integrations_l = {i.lower() for i in blueprint.integrations}
    workflows = [w.lower() for w in blueprint.workflows]
    knowledge = blueprint.knowledge or {}
    product_type = (blueprint.product_type or "").lower()
    industry = (blueprint.industry or "").lower()

    auth_ok = bool(auth.get("jwt") or auth.get("rbac") or auth.get("methods")) or (
        "auth" in modules_l or "authentication" in modules_l
    )
    if not auth_ok:
        warnings.append(
            BlueprintWarning(
                code="missing_auth",
                severity="error",
                message="Authentication / JWT / RBAC is missing from the blueprint.",
                field="authentication",
            )
        )

    saas_like = product_type in {"saas", "crm", "marketplace", "helpdesk"} or "subscription" in " ".join(
        workflows
    )
    billing_ok = bool(billing.get("enabled")) or "billing" in modules_l or "payments" in modules_l
    if saas_like and not billing_ok:
        warnings.append(
            BlueprintWarning(
                code="missing_billing",
                severity="warn",
                message="SaaS-style product without billing/metering — enable plans and payments.",
                field="billing",
            )
        )

    if not payments.get("providers") and billing_ok:
        warnings.append(
            BlueprintWarning(
                code="missing_payment_providers",
                severity="warn",
                message="Billing is enabled but no payment providers (Stripe/Razorpay) are listed.",
                field="payments",
            )
        )

    if "admin" not in pages_l and "admin" not in roles_l and "company_owner" not in roles_l:
        warnings.append(
            BlueprintWarning(
                code="missing_admin",
                severity="warn",
                message="No Admin page or admin/owner role detected.",
                field="pages",
            )
        )

    prompt_implies_ai = bool(ai) or bool(knowledge.get("enabled") or knowledge.get("rag"))
    if not ai and industry in {"healthcare", "crm", "saas"} and "chat" in " ".join(pages_l):
        warnings.append(
            BlueprintWarning(
                code="missing_ai",
                severity="info",
                message="Consider AI chat/RAG features for this product category.",
                field="ai_features",
            )
        )
    elif not ai and not prompt_implies_ai:
        warnings.append(
            BlueprintWarning(
                code="missing_ai",
                severity="info",
                message="No AI features listed — add chat/RAG if this is an AI product.",
                field="ai_features",
            )
        )

    if "storage" not in modules_l and "storage" not in integrations_l:
        warnings.append(
            BlueprintWarning(
                code="missing_storage",
                severity="warn",
                message="Storage module/integration missing for uploads and documents.",
                field="backend_modules",
            )
        )

    deploy_ok = bool(deployment.get("targets")) or bool(deployment.get("ssl"))
    if not deploy_ok:
        warnings.append(
            BlueprintWarning(
                code="missing_deployment",
                severity="warn",
                message="Deployment plan is empty — include Docker/Compose and SSL.",
                field="deployment",
            )
        )
    elif not deployment.get("monitoring"):
        warnings.append(
            BlueprintWarning(
                code="missing_monitoring",
                severity="info",
                message="Enable monitoring/healthchecks for production readiness.",
                field="deployment",
            )
        )

    if not blueprint.pages:
        warnings.append(
            BlueprintWarning(
                code="missing_pages",
                severity="error",
                message="No pages detected — add at least Landing/Login/Dashboard.",
                field="pages",
            )
        )
    if not blueprint.database_tables:
        warnings.append(
            BlueprintWarning(
                code="missing_database",
                severity="error",
                message="No database tables detected.",
                field="database_tables",
            )
        )
    if not blueprint.workflows:
        warnings.append(
            BlueprintWarning(
                code="missing_workflows",
                severity="info",
                message="No workflows listed — capture core business processes.",
                field="workflows",
            )
        )
    if "users" not in tables_l and "user" not in tables_l:
        warnings.append(
            BlueprintWarning(
                code="missing_users_table",
                severity="warn",
                message="Consider a users table for authentication and tenancy.",
                field="database_tables",
            )
        )
    if ai and not (knowledge.get("enabled") or knowledge.get("rag") or "knowledge" in modules_l):
        if "rag" in ai or "memory" in ai:
            warnings.append(
                BlueprintWarning(
                    code="missing_knowledge",
                    severity="info",
                    message="AI RAG/memory without Knowledge module — enable knowledge packs.",
                    field="knowledge",
                )
            )
    return warnings


def build_recommendations(blueprint: ProductBlueprint) -> BlueprintRecommendations:
    cat = (blueprint.marketplace_category or blueprint.product_type or "saas").lower()
    industry = (blueprint.industry or "general").lower()
    ai = [a.lower() for a in blueprint.ai_features]
    integrations = list(blueprint.integrations or [])
    integrations_l = {i.lower() for i in integrations}

    templates = _uniq(
        [
            f"{cat}-starter",
            f"{industry}-website",
            f"{industry}-saas",
            "saas-dashboard",
            *(["crm-pipeline"] if industry == "crm" or cat == "crm" else []),
            *(["healthcare-clinic"] if industry == "healthcare" else []),
        ]
    )
    assets = _uniq(
        [
            f"marketplace/{cat}",
            "marketplace/billing-kit",
            *(["marketplace/booking-kit"] if any("book" in w.lower() for w in blueprint.workflows) else []),
            *(["marketplace/ai-widget"] if ai else []),
        ]
    )

    agents: List[str] = []
    if ai:
        agents.append(f"{industry}-assistant")
        if "appointment_assistant" in ai or any("appoint" in w.lower() for w in blueprint.workflows):
            agents.append("booking-agent")
        if "chat" in ai:
            agents.append("support-chat-agent")
        if "rag" in ai:
            agents.append("knowledge-rag-agent")
        if "voice" in ai:
            agents.append("voice-agent")
    else:
        agents.append("generic-support-agent")

    packs: List[str] = []
    knowledge = blueprint.knowledge or {}
    if knowledge.get("enabled") or knowledge.get("rag") or "rag" in ai:
        packs.extend([f"{industry}-faq", "onboarding-docs", "policy-handbook"])
        packs.extend(_as_str_list(knowledge.get("packs")))

    for must in ("email", "webhooks", "storage"):
        if must not in integrations_l:
            integrations.append(must)
    if (blueprint.billing or {}).get("enabled"):
        for pay in ("stripe", "razorpay"):
            if pay not in integrations_l:
                integrations.append(pay)

    return BlueprintRecommendations(
        templates=templates[:8],
        marketplace_assets=assets[:8],
        agents=_uniq(agents)[:8],
        knowledge_packs=_uniq(packs)[:8],
        integrations=_uniq(integrations)[:10],
    )


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _resolve_provider_model(db, company_id) -> Tuple[str, str]:
    from app.ai.gateway_workspace import get_or_create_workspace_settings
    from app.config.settings import settings

    ws = get_or_create_workspace_settings(db, company_id)
    provider = (ws.default_provider or settings.AI_PROVIDER or "openai").strip().lower()
    model = PROVIDER_DEFAULT_MODELS.get(provider, "gpt-4o-mini")
    return provider, model


async def _generate_ai_blueprint(
    *,
    prompt: str,
    company_id,
    user_id,
    db,
) -> ProductBlueprint:
    from app.ai.schema import GenerateRequest
    from app.ai.service import AIService

    provider, model = _resolve_provider_model(db, company_id)
    svc = AIService(db)
    user_prompt = (
        f"{ARCHITECT_SYSTEM}\n\n"
        f"Product idea to blueprint:\n\"\"\"\n{prompt.strip()}\n\"\"\"\n\n"
        "Return the JSON object now."
    )
    result = await svc.generate(
        company_id=company_id,
        user_id=user_id,
        payload=GenerateRequest(
            prompt=user_prompt,
            provider=provider,
            model=model,
            temperature=0.15,
            max_tokens=3500,
        ),
    )
    parsed = _extract_json(result.content)
    if not parsed:
        raise ValueError("AI Gateway returned non-JSON blueprint content")
    missing = [k for k in REQUIRED_BLUEPRINT_KEYS if k not in parsed]
    if len(missing) > 6:
        raise ValueError(f"AI blueprint missing too many keys: {missing}")
    blueprint = normalize_ai_blueprint(parsed)
    if not ai_blueprint_is_usable(blueprint):
        raise ValueError("AI blueprint too sparse to accept")
    return blueprint


async def architect_blueprint(
    *,
    prompt: str,
    company_id,
    user_id,
    db,
    use_ai: bool = True,
) -> Tuple[ProductBlueprint, str]:
    """AI Gateway first. Heuristic only if AI is disabled or fails. Never merge/overwrite AI."""
    if use_ai:
        try:
            blueprint = await _generate_ai_blueprint(
                prompt=prompt,
                company_id=company_id,
                user_id=user_id,
                db=db,
            )
            logger.info(
                "studio_architect_ai_ok industry=%s pages=%s tables=%s",
                blueprint.industry,
                len(blueprint.pages),
                len(blueprint.database_tables),
            )
            return blueprint, "ai_gateway"
        except Exception as exc:
            logger.warning("studio_architect_ai_failed fallback=heuristic err=%s", exc)

    return build_heuristic_blueprint(prompt), "heuristic"
