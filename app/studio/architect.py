"""Deterministic + AI Gateway product architect (no code generation)."""
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

ARCHITECT_SYSTEM = """You are THTWAAT Product Architect.
Return ONLY valid JSON for a product blueprint with these keys:
industry, product_type, target_users (array), pages (array), dashboard_modules (array),
backend_modules (array), database_tables (array), roles (array), permissions (array),
authentication (object), billing (object), payments (object), ai_features (array),
knowledge (object), workflows (array), integrations (array), deployment (object),
marketplace_category (string), estimated_complexity (string), estimated_build_time (string).
Do not generate code. Do not wrap in markdown."""


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


def build_heuristic_blueprint(prompt: str) -> ProductBlueprint:
    """Reuse Product Generator analyzer signals — no duplicate industry detection."""
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
                *([ "Patients", "Doctors"] if industry == "healthcare" else []),
                *([ "Sales team"] if industry == "crm" else []),
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
                *([ "appointment_booking"] if "booking" in features or "appointment" in text else []),
                *([ "lead_capture"] if "leads" in features else []),
                *([ "human_handoff"] if "ai_chat" in features else []),
                "user_onboarding",
            ]
        ),
        integrations=_uniq(
            [
                *([ "stripe", "razorpay"] if "payments" in features or "billing" in text else []),
                *([ "email"] if True else []),
                *([ "webhooks"] if "webhook" in text else ["webhooks"]),
                *([ "storage"] if True else []),
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
    ai = [a.lower() for a in blueprint.ai_features]
    auth = blueprint.authentication or {}
    billing = blueprint.billing or {}
    deployment = blueprint.deployment or {}
    integrations_l = {i.lower() for i in blueprint.integrations}

    if not auth.get("jwt") and "auth" not in modules_l and "authentication" not in modules_l:
        warnings.append(
            BlueprintWarning(
                code="missing_auth",
                severity="error",
                message="Authentication / JWT is missing from the blueprint.",
                field="authentication",
            )
        )
    if not billing.get("enabled") and "billing" not in modules_l:
        warnings.append(
            BlueprintWarning(
                code="missing_billing",
                severity="warn",
                message="Billing is not enabled — add plans/metering for SaaS monetization.",
                field="billing",
            )
        )
    if "admin" not in pages_l and "admin" not in {r.lower() for r in blueprint.roles}:
        warnings.append(
            BlueprintWarning(
                code="missing_admin",
                severity="warn",
                message="No Admin page or admin role detected.",
                field="pages",
            )
        )
    if not ai:
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
    if not deployment.get("targets") and not deployment.get("ssl"):
        warnings.append(
            BlueprintWarning(
                code="missing_deployment",
                severity="warn",
                message="Deployment plan is empty — include Docker/Compose and SSL.",
                field="deployment",
            )
        )
    return warnings


def build_recommendations(blueprint: ProductBlueprint) -> BlueprintRecommendations:
    cat = (blueprint.marketplace_category or blueprint.product_type or "saas").lower()
    industry = (blueprint.industry or "general").lower()
    templates = [f"{cat}-starter", f"{industry}-website", "saas-dashboard"]
    assets = [f"marketplace/{cat}", "marketplace/billing-kit"]
    agents = []
    if blueprint.ai_features:
        agents.append(f"{industry}-assistant")
        if "appointment_assistant" in blueprint.ai_features:
            agents.append("booking-agent")
        if "chat" in blueprint.ai_features:
            agents.append("support-chat-agent")
    else:
        agents.append("generic-support-agent")
    packs = []
    if (blueprint.knowledge or {}).get("enabled"):
        packs.extend([f"{industry}-faq", "onboarding-docs"])
    integrations = list(blueprint.integrations or [])
    for must in ("stripe", "razorpay", "email", "webhooks"):
        if must not in {i.lower() for i in integrations}:
            integrations.append(must)
    return BlueprintRecommendations(
        templates=_uniq(templates)[:6],
        marketplace_assets=_uniq(assets)[:6],
        agents=_uniq(agents)[:6],
        knowledge_packs=_uniq(packs)[:6],
        integrations=_uniq(integrations)[:8],
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


def merge_blueprint(base: ProductBlueprint, overlay: Dict[str, Any]) -> ProductBlueprint:
    data = base.model_dump()
    for key, value in overlay.items():
        if key not in data:
            data[key] = value
            continue
        if isinstance(value, list) and isinstance(data[key], list):
            data[key] = _uniq([str(x) for x in data[key]] + [str(x) for x in value])
        elif isinstance(value, dict) and isinstance(data[key], dict):
            merged = dict(data[key])
            merged.update(value)
            data[key] = merged
        elif value not in (None, "", []):
            data[key] = value
    return ProductBlueprint.model_validate(data)


async def architect_blueprint(
    *,
    prompt: str,
    company_id,
    user_id,
    db,
    use_ai: bool = True,
) -> Tuple[ProductBlueprint, str]:
    """Build blueprint via heuristic, optionally enrich with AI Gateway."""
    base = build_heuristic_blueprint(prompt)
    if not use_ai:
        return base, "heuristic"

    try:
        from app.ai.schema import GenerateRequest
        from app.ai.service import AIService
        from app.config.settings import settings

        model = getattr(settings, "AI_DEFAULT_MODEL", None) or "gpt-4o-mini"
        provider = getattr(settings, "AI_PROVIDER", None) or "openai"
        svc = AIService(db)
        result = await svc.generate(
            company_id=company_id,
            user_id=user_id,
            payload=GenerateRequest(
                prompt=f"{ARCHITECT_SYSTEM}\n\nProduct idea:\n{prompt}",
                provider=provider,
                model=model,
                temperature=0.2,
                max_tokens=2500,
            ),
        )
        parsed = _extract_json(result.content)
        if parsed:
            return merge_blueprint(base, parsed), "ai_gateway"
    except Exception as exc:
        logger.info("Studio architect AI enrichment skipped: %s", exc)

    return base, "heuristic"
