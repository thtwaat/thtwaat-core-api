"""Unit tests for Studio Product Architect."""
from __future__ import annotations

import pytest

from app.studio.architect import (
    build_heuristic_blueprint,
    build_recommendations,
    validate_blueprint,
)
from app.studio.schemas import ProductBlueprint


@pytest.mark.unit
def test_hospital_prompt_blueprint():
    bp = build_heuristic_blueprint(
        "Create a Hospital Management SaaS with AI appointment booking, "
        "patient chat, billing, admin dashboard and website."
    )
    assert bp.industry == "healthcare"
    assert bp.product_type in {"saas", "website"}
    assert any("admin" in p.lower() for p in bp.pages) or "admin" in {r.lower() for r in bp.roles}
    assert bp.billing.get("enabled") is True or "Billing" in bp.backend_modules
    assert bp.ai_features
    assert "appointments" in bp.database_tables or "bookings" in bp.database_tables
    assert bp.marketplace_category


@pytest.mark.unit
def test_validation_detects_missing_pieces():
    thin = ProductBlueprint(
        industry="general",
        product_type="saas",
        pages=["Landing"],
        backend_modules=[],
        roles=["member"],
        authentication={},
        billing={"enabled": False},
        ai_features=[],
        integrations=[],
        deployment={},
    )
    warnings = validate_blueprint(thin)
    codes = {w.code for w in warnings}
    assert "missing_auth" in codes
    assert "missing_billing" in codes
    assert "missing_admin" in codes
    assert "missing_ai" in codes
    assert "missing_storage" in codes
    assert "missing_deployment" in codes


@pytest.mark.unit
def test_recommendations_for_ai_product():
    bp = build_heuristic_blueprint("CRM SaaS with AI chat, RAG knowledge and Stripe billing")
    recs = build_recommendations(bp)
    assert recs.templates
    assert recs.agents
    assert any("stripe" in i.lower() or "razorpay" in i.lower() for i in recs.integrations)
