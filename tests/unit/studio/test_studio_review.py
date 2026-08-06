"""Unit tests for Studio Review Center & Build Approval."""
from __future__ import annotations

import base64
import json

import pytest

from app.studio.ai_generator import generate_ai_manifest
from app.studio.backend_generator import generate_backend_manifest
from app.studio.composer import compose_modules
from app.studio.frontend_generator import generate_frontend_manifest
from app.studio.infrastructure_generator import generate_infrastructure_manifest
from app.studio.review import (
    build_review_manifest,
    can_approve,
    export_review_payload,
    list_required_secrets,
    validate_review,
)
from app.studio.schemas import DependencyEdge, ProductBlueprint


def _hospital_blueprint() -> ProductBlueprint:
    return ProductBlueprint(
        industry="healthcare",
        product_type="saas",
        pages=["Landing", "Login", "Admin", "Patients", "Appointments", "Billing", "Dashboard"],
        dashboard_modules=["Schedule"],
        backend_modules=["Auth", "Billing", "AI Gateway", "Knowledge", "Storage", "Appointments"],
        database_tables=["users", "patients", "appointments"],
        roles=["admin", "doctor"],
        authentication={"jwt": True, "rbac": True},
        billing={"enabled": True},
        payments={"providers": ["razorpay"]},
        ai_features=["chat", "rag", "appointment_assistant", "memory"],
        knowledge={"enabled": True, "rag": True},
        workflows=["appointment_booking", "human_handoff"],
        integrations=["email", "storage", "widget"],
        deployment={"targets": ["docker", "vps"], "ssl": True, "domain": "hospital.example.com"},
        marketplace_category="saas",
        estimated_complexity="high",
        estimated_build_time="4-8 weeks",
    )


def _full_pipeline():
    bp = _hospital_blueprint()
    modules = compose_modules(bp)
    edges = [
        DependencyEdge(key=m.key, label=m.label, depends_on=list(m.depends_on or []))
        for m in modules
    ]
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
    ai = generate_ai_manifest(
        blueprint=bp,
        modules=modules,
        backend=backend,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
    )
    infra = generate_infrastructure_manifest(
        blueprint=bp,
        modules=modules,
        backend=backend,
        ai=ai,
        project_title="Hospital Ops",
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
        ai_version=1,
    )
    return bp, modules, edges, frontend, backend, ai, infra


@pytest.mark.unit
def test_review_aggregates_all_manifests():
    bp, modules, edges, frontend, backend, ai, infra = _full_pipeline()
    review = build_review_manifest(
        project_title="Hospital Ops",
        project_status="approved",
        blueprint=bp,
        modules=modules,
        dependency_graph=edges,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        frontend_status="approved",
        backend_version=1,
        backend_status="approved",
        ai_version=1,
        ai_status="draft",
        infra_version=1,
        infra_status="draft",
    )
    ids = {a.id for a in review.artifacts}
    assert ids == {"blueprint", "build_plan", "frontend", "backend", "ai", "infrastructure"}
    assert all(a.present for a in review.artifacts)
    assert review.architecture.pages
    assert review.architecture.database
    assert review.architecture.api
    assert review.architecture.ai_providers
    assert review.architecture.dependency_graph
    assert review.architecture.deployment_targets
    assert review.estimate.generated_files > 0
    assert review.estimate.rest_apis > 0
    assert review.estimate.database_tables > 0
    assert review.estimate.ai_cost_monthly_usd >= 0
    assert review.estimate.infrastructure_cost_monthly_usd > 0
    assert review.ready_to_approve is True
    assert "does not" in review.note.lower() or "no source" in review.note.lower()


@pytest.mark.unit
def test_validation_detects_gaps():
    weak = ProductBlueprint(
        industry="general",
        product_type="saas",
        ai_features=["chat"],
        billing={"enabled": True},
        integrations=["email"],
        deployment={},
        estimated_complexity="low",
    )
    issues = validate_review(
        blueprint=weak,
        modules=[],
        frontend=None,
        backend=None,
        ai=None,
        infra=None,
    )
    codes = {i.code for i in issues}
    assert "missing_frontend" in codes
    assert "missing_backend" in codes
    assert "missing_ai" in codes
    assert "missing_infrastructure" in codes
    assert "missing_ai_provider" in codes
    assert "missing_deployment_target" in codes
    assert "missing_email_provider" in codes
    assert "missing_secrets" in codes


@pytest.mark.unit
def test_required_secrets_catalog():
    bp, modules, _edges, _fe, _be, ai, infra = _full_pipeline()
    secrets = list_required_secrets(blueprint=bp, modules=modules, ai=ai, infra=infra)
    labels = {s.id for s in secrets}
    for required in (
        "openai",
        "gemini",
        "anthropic",
        "openrouter",
        "stripe",
        "razorpay",
        "smtp",
        "storage",
        "analytics",
    ):
        assert required in labels
    razorpay = next(s for s in secrets if s.id == "razorpay")
    assert razorpay.required is True
    smtp = next(s for s in secrets if s.id == "smtp")
    assert smtp.required is True


@pytest.mark.unit
def test_approval_gate():
    bp, modules, edges, frontend, backend, ai, infra = _full_pipeline()
    incomplete = build_review_manifest(
        project_title="Partial",
        project_status="approved",
        blueprint=bp,
        modules=modules,
        dependency_graph=edges,
        frontend=frontend,
        backend=backend,
        ai=None,
        infra=None,
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
    )
    ok, reason = can_approve(incomplete)
    assert ok is False
    assert reason

    complete = build_review_manifest(
        project_title="Complete",
        project_status="approved",
        blueprint=bp,
        modules=modules,
        dependency_graph=edges,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
        ai_version=1,
        infra_version=1,
    )
    ok2, _ = can_approve(complete)
    assert ok2 is True


@pytest.mark.unit
def test_export_json_markdown_pdf():
    bp, modules, edges, frontend, backend, ai, infra = _full_pipeline()
    review = build_review_manifest(
        project_title="Hospital Ops",
        project_status="approved",
        blueprint=bp,
        modules=modules,
        dependency_graph=edges,
        frontend=frontend,
        backend=backend,
        ai=ai,
        infra=infra,
        blueprint_version=1,
        build_plan_version=1,
        frontend_version=1,
        backend_version=1,
        ai_version=1,
        infra_version=1,
    )
    j = export_review_payload(review=review, kind="review", format="json")
    assert j["format"] == "json"
    parsed = json.loads(j["content"])
    assert parsed["product_name"] == "Hospital Ops"

    md = export_review_payload(review=review, kind="review", format="markdown")
    assert md["format"] == "markdown"
    assert "# THTWAAT Studio Review" in md["content"]

    pdf = export_review_payload(review=review, kind="review", format="pdf")
    assert pdf["format"] == "pdf"
    assert pdf["encoding"] == "base64"
    raw = base64.b64decode(pdf["content"])
    assert raw.startswith(b"%PDF")

    bp_export = export_review_payload(
        review=review, kind="blueprint", format="json", blueprint=bp
    )
    assert "industry" in json.loads(bp_export["content"])

    plan_export = export_review_payload(
        review=review,
        kind="build_plan",
        format="markdown",
        build_plan={"modules": [{"key": "auth"}], "version": 1},
    )
    assert "Build Plan" in plan_export["content"]
