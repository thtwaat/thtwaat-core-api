"""Unit tests for Studio Backend Generator."""
from __future__ import annotations

import pytest

from app.studio.backend_generator import (
    generate_api_manifest,
    generate_backend_manifest,
    generate_database_manifest,
    generate_openapi_preview,
    generate_queue_plan,
    generate_rbac_manifest,
    generate_service_manifest,
)
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
        database_tables=["users", "patients", "appointments", "invoices"],
        roles=["company_owner", "admin", "doctor", "patient"],
        permissions=["patients:read"],
        authentication={"jwt": True, "rbac": True},
        billing={"enabled": True},
        payments={"providers": ["razorpay"]},
        ai_features=["chat", "rag"],
        knowledge={"enabled": True, "rag": True},
        workflows=["appointment_booking"],
        integrations=["email", "storage"],
        deployment={"targets": ["docker"]},
        marketplace_category="saas",
    )


@pytest.mark.unit
def test_api_manifest_reuses_platform_and_adds_custom():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
    )
    api = generate_api_manifest(blueprint=bp, modules=modules, frontend=frontend)
    assert api.endpoints
    assert api.reuse_endpoint_count > 0
    paths = {e.path for e in api.endpoints}
    assert any("/api/v1/auth" in p or "/api/v1/payments" in p for p in paths)
    assert any("/v2/agents" in p or "/v2/knowledge" in p for p in paths)
    # Custom patients/appointments
    assert any("custom" in e.path for e in api.endpoints)
    # Validation / pagination / search present on list ops
    lists = [e for e in api.endpoints if e.operation == "list"]
    assert lists and all(e.pagination for e in lists)
    assert any(e.search for e in lists)
    assert any(e.permissions for e in api.endpoints)


@pytest.mark.unit
def test_database_manifest_and_migrations():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
    )
    db = generate_database_manifest(blueprint=bp, modules=modules, frontend=frontend)
    names = {t.name for t in db.tables}
    assert "users" in names or db.reuse_table_count > 0
    assert db.custom_table_count >= 1
    assert db.migrations
    assert db.relationships
    assert db.enums


@pytest.mark.unit
def test_rbac_roles_permissions_policies():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
    )
    api = generate_api_manifest(blueprint=bp, modules=modules, frontend=frontend)
    rbac = generate_rbac_manifest(blueprint=bp, api=api)
    assert "company_owner" in [r.lower() for r in rbac.roles] or "admin" in [
        r.lower() for r in rbac.roles
    ]
    assert rbac.permissions
    assert rbac.policies
    assert rbac.reuse is True
    assert rbac.platform_ref == "app/auth"


@pytest.mark.unit
def test_queue_plan_covers_email_ai_import_export():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    queues = generate_queue_plan(blueprint=bp, modules=modules)
    kinds = {q.kind for q in queues}
    assert "emails" in kinds or "notifications" in kinds
    assert "ai_jobs" in kinds
    assert "imports" in kinds
    assert "exports" in kinds


@pytest.mark.unit
def test_backend_manifest_openapi_and_no_platform_duplicates():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
    )
    manifest = generate_backend_manifest(
        blueprint=bp,
        modules=modules,
        frontend=frontend,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
    )
    assert manifest.api.endpoints
    assert manifest.database.tables
    assert manifest.services
    assert manifest.rbac.roles
    assert manifest.storage
    assert manifest.queues
    assert manifest.openapi.paths
    assert manifest.summary.reuse_percent >= 40
    # Reused Auth/Billing services present
    names = {s.name.lower() for s in manifest.services}
    assert any("auth" in n for n in names)
    assert any("bill" in n for n in names)
    # OpenAPI preview
    openapi = generate_openapi_preview(product_name="Hospital Ops", api=manifest.api)
    assert openapi.openapi.startswith("3.")
    assert openapi.paths
    # No deploy / codegen note
    assert "does not emit source" in manifest.note.lower() or "preview" in manifest.note.lower()


@pytest.mark.unit
def test_services_include_webhooks_and_jobs():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    frontend = generate_frontend_manifest(
        blueprint=bp,
        modules=modules,
        project_title="Hospital",
        blueprint_version=1,
        build_plan_version=1,
    )
    services = generate_service_manifest(blueprint=bp, modules=modules, frontend=frontend)
    kinds = {s.kind for s in services}
    assert "business" in kinds
    assert "webhook" in kinds or "job" in kinds or "event" in kinds
