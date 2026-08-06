"""Unit tests for Studio AI Generator."""
from __future__ import annotations

import pytest

from app.ai.gateway_workspace import KNOWN_PROVIDERS
from app.studio.ai_generator import (
    generate_ai_manifest,
    generate_prompt_library,
    recommend_models,
    select_providers,
)
from app.studio.backend_generator import generate_backend_manifest
from app.studio.composer import compose_modules
from app.studio.frontend_generator import generate_frontend_manifest
from app.studio.schemas import ProductBlueprint


def _hospital_blueprint() -> ProductBlueprint:
    return ProductBlueprint(
        industry="healthcare",
        product_type="saas",
        pages=["Landing", "Login", "Admin", "Patients", "Appointments", "Billing", "Dashboard"],
        dashboard_modules=["Schedule"],
        backend_modules=["Auth", "Billing", "AI Gateway", "Knowledge", "Storage", "Appointments"],
        database_tables=["users", "patients", "appointments"],
        roles=["admin", "doctor"],
        authentication={"jwt": True},
        billing={"enabled": True},
        payments={"providers": ["razorpay"]},
        ai_features=["chat", "rag", "appointment_assistant", "memory"],
        knowledge={"enabled": True, "rag": True},
        workflows=["appointment_booking", "human_handoff"],
        integrations=["email", "storage", "widget"],
        deployment={"targets": ["docker"]},
        marketplace_category="saas",
        estimated_complexity="high",
    )


@pytest.mark.unit
def test_provider_selection_covers_gateway_providers():
    providers = select_providers(_hospital_blueprint())
    names = {p.provider for p in providers}
    for required in KNOWN_PROVIDERS:
        assert required in names
    assert providers[0].recommended_primary is True
    assert all(p.capabilities for p in providers)
    assert "openai" in names and "gemini" in names and "ollama" in names
    assert "anthropic" in names and "openrouter" in names


@pytest.mark.unit
def test_model_recommendations_include_task_models():
    bp = _hospital_blueprint()
    providers = select_providers(bp)
    models = recommend_models(bp, providers)
    tasks = {m.task for m in models}
    assert "chat" in tasks
    assert "rag" in tasks
    assert "embeddings" in tasks
    assert "tools" in tasks
    assert "moderation" in tasks


@pytest.mark.unit
def test_prompt_library_and_validation():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
    )
    backend = generate_backend_manifest(
        blueprint=bp,
        modules=modules,
        frontend=frontend,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
    )
    manifest = generate_ai_manifest(
        blueprint=bp,
        modules=modules,
        backend=backend,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
    )
    assert manifest.agents
    assert all(a.reuse for a in manifest.agents)
    assert manifest.capabilities.get("streaming") is True
    assert manifest.capabilities.get("safety") is True
    assert manifest.capabilities.get("moderation") is True
    assert manifest.capabilities.get("lead_capture") is True
    assert manifest.capabilities.get("human_handoff") is True
    assert manifest.capabilities.get("multi_language") is True
    assert manifest.memory.get("enabled") is True
    assert manifest.knowledge.get("enabled") is True
    assert "gateway" in manifest.runtime
    assert "does not emit" in manifest.note.lower() or "preview" in manifest.note.lower()
    prompts = generate_prompt_library(bp, manifest.agents)
    ids = {p.id for p in prompts}
    assert "system_core" in ids
    assert "rag_answer" in ids
    assert "lead_capture" in ids
    assert "human_handoff" in ids
    assert "moderation_precheck" in ids


@pytest.mark.unit
def test_ai_manifest_tools_workflows_cost():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
    )
    backend = generate_backend_manifest(
        blueprint=bp,
        modules=modules,
        frontend=frontend,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
    )
    manifest = generate_ai_manifest(
        blueprint=bp,
        modules=modules,
        backend=backend,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
    )
    tool_ids = {t.id for t in manifest.tools}
    assert "search_knowledge" in tool_ids
    assert "handoff_human" in tool_ids
    assert manifest.workflows
    assert manifest.cost.estimated_monthly_usd >= 0
    assert manifest.cost.metering_ref
    assert manifest.summary.reuse_percent >= 50
    assert manifest.providers[0].platform_ref == "app/ai"


@pytest.mark.unit
def test_voice_vision_plan_only_when_requested():
    bp = _hospital_blueprint()
    bp.ai_features = ["chat", "voice", "vision"]
    providers = select_providers(bp)
    models = recommend_models(bp, providers)
    voice = next(m for m in models if m.task == "voice")
    vision = next(m for m in models if m.task == "vision")
    assert voice.plan_only is True
    assert vision.plan_only is True
