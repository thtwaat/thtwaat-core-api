"""Unit tests for Template Registry & Module Composer."""
from __future__ import annotations

import pytest

from app.studio.composer import (
    build_dependency_graph,
    compose_blueprint,
    compose_modules,
    detect_required_keys,
    order_build_plan,
    summarize_plan,
)
from app.studio.registry import TEMPLATE_REGISTRY, list_registry, resolve_alias
from app.studio.schemas import ModuleKind, ProductBlueprint


def _hospital_blueprint() -> ProductBlueprint:
    return ProductBlueprint(
        industry="healthcare",
        product_type="saas",
        target_users=["Doctors", "Patients", "Admins"],
        pages=["Landing", "Login", "Admin", "Patients", "Appointments", "Billing", "Dashboard"],
        dashboard_modules=["Schedule", "Revenue"],
        backend_modules=[
            "Auth",
            "Users",
            "RBAC",
            "Billing",
            "AI Gateway",
            "Knowledge",
            "Storage",
            "Appointments",
        ],
        database_tables=["users", "patients", "appointments", "invoices"],
        roles=["company_owner", "admin", "doctor", "patient"],
        permissions=["patients:read", "billing:manage"],
        authentication={"methods": ["email_password"], "jwt": True, "rbac": True},
        billing={"enabled": True, "plans": ["starter", "pro"]},
        payments={"providers": ["razorpay", "stripe"]},
        ai_features=["chat", "rag", "appointment_assistant"],
        knowledge={"enabled": True, "rag": True},
        workflows=["appointment_booking", "patient_intake"],
        integrations=["razorpay", "email", "storage", "widget"],
        deployment={"targets": ["docker"], "ssl": True, "monitoring": True},
        marketplace_category="saas",
        estimated_complexity="high",
    )


@pytest.mark.unit
def test_registry_covers_required_templates():
    labels = {e.label for e in list_registry()}
    for required in (
        "Landing Page",
        "Dashboard",
        "Authentication",
        "Billing",
        "Payments",
        "Admin",
        "Knowledge",
        "AI Agent",
        "Widget",
        "Analytics",
        "Notifications",
        "Marketplace",
        "Publisher",
        "Storage",
        "RBAC",
        "Database",
    ):
        assert required in labels
    assert resolve_alias("Auth") == "authentication"
    assert resolve_alias("AI Gateway") == "ai_agent"
    assert "authentication" in TEMPLATE_REGISTRY


@pytest.mark.unit
def test_module_mapping_reuses_platform_modules():
    modules = compose_modules(_hospital_blueprint())
    by_key = {m.key: m for m in modules}
    assert "authentication" in by_key
    assert by_key["authentication"].kind == ModuleKind.EXISTING
    assert by_key["authentication"].platform_ref == "app/auth"
    assert "billing" in by_key
    assert by_key["billing"].kind == ModuleKind.EXISTING
    assert "ai_agent" in by_key
    assert "knowledge" in by_key
    assert "marketplace" in by_key
    assert "publisher" in by_key
    # Domain module not in registry → custom
    customs = [m for m in modules if m.kind == ModuleKind.CUSTOM]
    assert any("Appointments" in m.label for m in customs)


@pytest.mark.unit
def test_dependency_graph_auth_billing_ai():
    modules = compose_modules(_hospital_blueprint())
    graph = {e.key: e.depends_on for e in build_dependency_graph(modules)}
    assert "authentication" in graph
    assert graph["rbac"] == ["authentication"] or "authentication" in graph["rbac"]
    assert "billing" in graph
    assert "authentication" in graph["billing"] or "database" in graph["billing"]
    assert "payments" in graph
    assert "billing" in graph["payments"]
    assert "ai_agent" in graph
    assert "knowledge" in graph["ai_agent"] or "authentication" in graph["ai_agent"]


@pytest.mark.unit
def test_build_plan_ordered_phases():
    result = compose_blueprint(_hospital_blueprint())
    keys = [s.key for s in result.build_plan]
    assert keys[-1] == "deployment"
    assert keys.index("authentication") < keys.index("billing")
    assert keys.index("database") < keys.index("dashboard")
    assert keys.index("billing") < keys.index("ai_agent")
    assert "deployment" in keys
    # Deployment is planning only
    deploy = result.build_plan[-1]
    assert deploy.note and "does not deploy" in deploy.note.lower()


@pytest.mark.unit
def test_reuse_detection_high_for_hospital():
    modules = compose_modules(_hospital_blueprint())
    summary = summarize_plan(modules, blueprint=_hospital_blueprint())
    assert summary.reuse_percent >= 70
    assert summary.existing_count + summary.marketplace_count >= summary.custom_count
    assert summary.module_count == len(modules)


@pytest.mark.unit
def test_detect_required_keys_minimal_landing():
    bp = ProductBlueprint(
        industry="growth",
        product_type="landing",
        pages=["Landing", "Contact"],
        backend_modules=[],
        database_tables=[],
        roles=[],
        authentication={},
        billing={},
        payments={},
        ai_features=[],
        knowledge={},
        workflows=[],
        integrations=[],
        deployment={},
    )
    keys = detect_required_keys(bp)
    assert "landing_page" in keys
    assert "authentication" not in keys or "landing_page" in keys


@pytest.mark.unit
def test_order_build_plan_respects_deps():
    modules = compose_modules(_hospital_blueprint())
    steps = order_build_plan(modules)
    index = {s.key: s.order for s in steps if s.key != "deployment"}
    if "payments" in index and "billing" in index:
        assert index["billing"] < index["payments"]
    if "widget" in index and "ai_agent" in index:
        assert index["ai_agent"] < index["widget"]
