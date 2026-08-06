"""Unit tests for Studio Frontend Generator."""
from __future__ import annotations

import pytest

from app.studio.composer import compose_modules
from app.studio.frontend_generator import (
    generate_frontend_manifest,
    generate_navigation,
    generate_page_manifest,
    generate_routes,
)
from app.studio.schemas import ComposedModule, ModuleKind, ProductBlueprint


def _hospital_blueprint() -> ProductBlueprint:
    return ProductBlueprint(
        industry="healthcare",
        product_type="saas",
        pages=["Landing", "Login", "Admin", "Patients", "Appointments", "Billing", "Dashboard"],
        dashboard_modules=["Schedule", "Revenue"],
        backend_modules=["Auth", "Billing", "AI Gateway", "Knowledge", "Storage", "Appointments"],
        database_tables=["users", "patients", "appointments", "invoices"],
        roles=["admin", "doctor"],
        authentication={"jwt": True, "rbac": True},
        billing={"enabled": True},
        payments={"providers": ["razorpay"]},
        ai_features=["chat", "rag"],
        knowledge={"enabled": True, "rag": True},
        workflows=["appointment_booking"],
        integrations=["email", "storage", "widget"],
        deployment={"targets": ["docker"]},
        marketplace_category="saas",
    )


@pytest.mark.unit
def test_frontend_manifest_reuses_existing_pages():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    manifest = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
    )
    page_ids = {p.id for p in manifest.pages}
    assert "login" in page_ids
    assert "dashboard" in page_ids
    assert "billing" in page_ids
    assert "agents" in page_ids
    assert "admin" in page_ids
    login = next(p for p in manifest.pages if p.id == "login")
    assert login.kind == "reuse"
    assert login.reuse and "/login" in (login.reuse.route or login.route)
    assert manifest.summary.reuse_percent >= 50
    assert "app_shell" in manifest.design_system or "components/layout/app-shell.tsx" in manifest.design_system.values()


@pytest.mark.unit
def test_route_and_navigation_generation():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    pages, _forms, _warnings = generate_page_manifest(bp, modules)
    nav = generate_navigation(pages)
    routes = generate_routes(pages)
    assert nav
    assert any(n.route == "/app" for n in nav)
    assert any(n.label == "Billing" for n in nav)
    paths = [r.path for r in routes]
    assert "/login" in paths
    assert "/app" in paths
    assert "/app/billing" in paths
    # Nav items should map to routes
    nav_routes = {n.route for n in nav}
    assert nav_routes.issubset(set(paths))


@pytest.mark.unit
def test_custom_crud_screens_for_domain_pages():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    pages, forms, _ = generate_page_manifest(bp, modules)
    customs = [p for p in pages if p.kind == "generated_spec"]
    assert customs
    assert any("Patient" in p.title or "Appointment" in p.title for p in customs)
    for p in customs:
        assert p.crud is not None
        assert "list" in p.crud.operations
        assert p.responsive is True
        assert p.route.startswith("/app/custom/")
    assert forms
    assert any(not f.reuse for f in forms)


@pytest.mark.unit
def test_dashboard_cards_from_blueprint_modules():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    manifest = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
    )
    assert manifest.dashboard_cards
    titles = {c.get("title") for c in manifest.dashboard_cards}
    assert "Schedule" in titles or "Revenue" in titles or "Agents" in titles


@pytest.mark.unit
def test_reuse_detection_prefers_existing_over_custom():
    modules = [
        ComposedModule(
            key="authentication",
            label="Authentication",
            kind=ModuleKind.EXISTING,
            platform_ref="app/auth",
            reason="test",
        ),
        ComposedModule(
            key="dashboard",
            label="Dashboard",
            kind=ModuleKind.MARKETPLACE,
            platform_ref="apps/templates/saas",
            reason="test",
        ),
        ComposedModule(
            key="billing",
            label="Billing",
            kind=ModuleKind.EXISTING,
            platform_ref="app/payments",
            reason="test",
        ),
    ]
    bp = ProductBlueprint(
        industry="saas",
        product_type="saas",
        pages=["Login", "Dashboard", "Billing"],
        dashboard_modules=["Overview"],
        database_tables=["users"],
        authentication={"jwt": True},
        billing={"enabled": True},
    )
    pages, _, _ = generate_page_manifest(bp, modules)
    by_id = {p.id: p for p in pages}
    assert by_id["login"].kind == "reuse"
    assert by_id["dashboard"].kind == "reuse"
    assert by_id["billing"].kind == "reuse"
    assert not any(p.kind == "generated_spec" and p.title == "Login" for p in pages)


@pytest.mark.unit
def test_preview_blocks_present_on_pages():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    pages, _, _ = generate_page_manifest(bp, modules)
    for page in pages:
        assert isinstance(page.preview, dict)
        if page.kind == "generated_spec":
            assert "sample_rows" in page.preview or "blocks" in page.preview
